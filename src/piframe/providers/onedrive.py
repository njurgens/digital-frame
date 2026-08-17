"""OneDrive shared folder provider using the Badger token API."""

from __future__ import annotations

import base64
import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from piframe.album import Album
from piframe.image import IMAGE_EXTENSIONS, Image
from piframe.providers.base import BaseAlbumProvider

if TYPE_CHECKING:
    from piframe.config_store import ConfigStore

API_V2_0 = "https://my.microsoftpersonalcontent.com/_api/v2.0"
API_V2_1 = "https://my.microsoftpersonalcontent.com/_api/v2.1"
APP_ID = "00000000-0000-0000-0000-0000481710a4"

#: (connect, read) timeout in seconds for every Badger API and download call.
REQUEST_TIMEOUT: tuple[int, int] = (10, 60)
#: Stream download in 1 MiB chunks to keep SD-card write syscalls low.
DOWNLOAD_CHUNK = 1 << 20


def encode_url(url: str) -> str:
    """Base64-encode a share URL for the Badger API."""
    return base64.b64encode(url.encode()).rstrip(b"=").decode().replace("/", "_").replace("+", "-")


def _is_safe_name(name: str) -> bool:
    """True if a remote item name is a safe single path component.

    Rejects empty names, the two single-dot names, the parent-directory
    reference, any name containing a path separator, and any name containing
    a control character: newlines are legal in Linux filenames but would let
    a remote item forge log lines, since the sync code logs names verbatim.
    Together these keep names from the OneDrive API from escaping the cache
    directory (path traversal) or addressing the cache directory itself.
    """
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        return False
    return all(ord(ch) >= 0x20 and ch != "\x7f" for ch in name)


class OneDriveConfig:
    """OneDrive provider settings, read from the ``[sync.onedrive]`` section."""

    def __init__(self, config: ConfigStore) -> None:
        """Wrap the config store."""
        self._config = config

    @property
    def share_url(self) -> str:
        """OneDrive shared folder URL."""
        return str(self._config.read_nested("sync", "onedrive", "share_url", default=""))

    @property
    def password(self) -> str:
        """Share password (may be empty for passwordless shares)."""
        return str(self._config.read_nested("sync", "onedrive", "password", default=""))

    @property
    def cache_dir(self) -> Path:
        """Local directory where the provider stores downloaded images."""
        raw = self._config.read_nested(
            "sync", "onedrive", "cache_dir", default="~/.cache/piframe/onedrive"
        )
        return Path(str(raw)).expanduser()


class OneDriveProvider(BaseAlbumProvider):
    """Syncs a OneDrive shared folder into its own local cache directory.

    The provider owns its cache: it downloads new files, performs
    destructive cleanup (deletes cached files no longer present on the
    remote), and exposes the cached images as an album.
    """

    def __init__(self, config: OneDriveConfig) -> None:
        """Create the provider with its config wrapper."""
        super().__init__()
        self._config = config

    @property
    def storage_dir(self) -> Path:
        """Directory where this provider stores its image files."""
        return self._config.cache_dir

    # -- sync work -----------------------------------------------------------

    def _do_sync(self) -> Album:
        share_url = self._config.share_url
        if not share_url:
            raise RuntimeError("No OneDrive share URL configured")

        session = requests.Session()
        try:
            token = self._get_badger_token(session)
            encoded = encode_url(share_url)
            self._validate_password(session, encoded, share_url, self._config.password, token)
            root = self._redeem_share(session, encoded, token)

            cache_dir = self._config.cache_dir
            if "file" in root:
                self._download_single_file(session, root, cache_dir)
            else:
                drive_id = root["parentReference"]["driveId"]
                folder_id = root["id"]
                self._sync_folder(session, drive_id, folder_id, token, cache_dir)

            return self._build_album(cache_dir)
        finally:
            session.close()

    def _build_album(self, cache_dir: Path) -> Album:
        images: list[Image] = []
        if cache_dir.is_dir():
            for path in sorted(cache_dir.rglob("*")):
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                    images.append(Image(path))
        return Album.from_images(images)

    # -- Badger API calls ------------------------------------------------------

    def _get_badger_token(self, session: requests.Session) -> str:
        resp = session.post(
            "https://api-badgerp.svc.ms/v1.0/token",
            headers={"Content-Type": "application/json"},
            json={"appId": APP_ID},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["token"]

    def _validate_password(
        self,
        session: requests.Session,
        encoded_url: str,
        share_url: str,
        password: str,
        token: str,
    ) -> None:
        url = f"{API_V2_1}/shares/u!{encoded_url}/root/oneDrive.validatePermission"
        challenge = base64.b64encode(share_url.encode()).decode()
        resp = session.post(
            url,
            headers={
                "Authorization": f"Badger {token}",
                "Content-Type": "application/json",
            },
            json={"challengeToken": challenge, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            logging.error(
                "OneDrive password validation failed %s: %s", resp.status_code, resp.text
            )
            resp.raise_for_status()
        logging.info("OneDrive password validated")

    def _redeem_share(
        self, session: requests.Session, encoded_url: str, token: str
    ) -> dict[str, Any]:
        url = f"{API_V2_0}/shares/u!{encoded_url}/driveitem"
        params = {
            "$select": "id,parentReference,folder,bundle,remoteItem,name,file,@content.downloadUrl"
        }
        resp = session.post(
            url,
            headers={
                "Authorization": f"Badger {token}",
                "Prefer": "autoredeem",
                "Content-Type": "text/plain;charset=UTF-8",
            },
            params=params,
            data="",
            timeout=REQUEST_TIMEOUT,
        )
        if not resp.ok:
            logging.error("OneDrive share redemption failed %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
        return resp.json()

    # -- file transfer ---------------------------------------------------------

    def _download_single_file(
        self, session: requests.Session, item: dict[str, Any], dest: Path
    ) -> None:
        name = item["name"]
        if not _is_safe_name(name):
            logging.warning("OneDrive: skipping file with unsafe name %r", name)
            return
        dest.mkdir(parents=True, exist_ok=True, mode=0o700)
        dest_file = dest / name
        if dest_file.is_dir():
            logging.info("OneDrive: replacing stale dir %r with file", name)
            shutil.rmtree(dest_file)
        elif dest_file.is_file():
            logging.info("OneDrive: skip existing file %r", name)
        else:
            logging.info("OneDrive: downloading %r", name)
            self._download(session, item.get("@content.downloadUrl"), dest_file)
        # Destructive cleanup: a single-file share has exactly one remote
        # entry, so anything else in the cache dir is stale (e.g. the old
        # name after a remote rename).
        for local in list(dest.iterdir()):
            if local.name != name:
                if local.is_dir():
                    logging.info("OneDrive: deleting stale dir %r", local.name)
                    shutil.rmtree(local)
                else:
                    logging.info("OneDrive: deleting stale file %r", local.name)
                    local.unlink()

    def _sync_folder(
        self, session: requests.Session, drive_id: str, folder_id: str, token: str, dest: Path
    ) -> None:
        dest.mkdir(parents=True, exist_ok=True, mode=0o700)
        # name -> is_folder, for type-aware destructive cleanup
        remote_items: dict[str, bool] = {}

        url: str | None = f"{API_V2_0}/drives/{drive_id}/items/{folder_id}/children"
        # Request the download URL in the listing itself: without it, every
        # new file costs an extra per-item API round trip on first sync.
        # The continuation link (@odata.nextLink) already carries the
        # request's query parameters, so only the first page needs them.
        select: dict[str, str] | None = {"$select": "name,id,file,folder,@content.downloadUrl"}
        while url:
            resp = session.get(
                url,
                params=select,
                headers={"Authorization": f"Badger {token}"},
                timeout=REQUEST_TIMEOUT,
            )
            select = None
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                name = item["name"]
                if not _is_safe_name(name):
                    logging.warning("OneDrive: skipping item with unsafe name %r", name)
                    continue
                if "file" in item:
                    remote_items[name] = False
                    self._sync_file_item(session, drive_id, token, dest, item)
                elif "folder" in item:
                    remote_items[name] = True
                    self._sync_folder_item(session, drive_id, token, dest, item)
            url = data.get("@odata.nextLink")

        # Destructive cleanup: delete local entries missing from the remote,
        # or whose type (file vs folder) no longer matches it.  Iterate a
        # materialized list: deleting entries while a lazy iterdir() stream
        # is still open can make readdir skip entries on Linux.
        for local in list(dest.iterdir()):
            remote_is_folder = remote_items.get(local.name)
            if remote_is_folder is None or remote_is_folder != local.is_dir():
                if local.is_dir():
                    logging.info("OneDrive: deleting stale dir %r", local.name)
                    shutil.rmtree(local)
                else:
                    logging.info("OneDrive: deleting stale file %r", local.name)
                    local.unlink()

    def _sync_file_item(
        self,
        session: requests.Session,
        drive_id: str,
        token: str,
        dest: Path,
        item: dict[str, Any],
    ) -> None:
        """Sync one file entry: replace a stale dir, skip if present, else download."""
        name = item["name"]
        dest_file = dest / name
        if dest_file.is_dir():
            logging.info("OneDrive: replacing stale dir %r with file", name)
            shutil.rmtree(dest_file)
        elif dest_file.is_file():
            logging.info("OneDrive: skip %r", name)
            return
        logging.info("OneDrive: downloading %r", name)
        dl_url = item.get("@content.downloadUrl")
        if not dl_url:
            item_resp = session.get(
                f"{API_V2_0}/drives/{drive_id}/items/{item['id']}",
                headers={"Authorization": f"Badger {token}"},
                timeout=REQUEST_TIMEOUT,
            )
            item_resp.raise_for_status()
            dl_url = item_resp.json().get("@content.downloadUrl")
        self._download(session, dl_url, dest_file)

    def _sync_folder_item(
        self,
        session: requests.Session,
        drive_id: str,
        token: str,
        dest: Path,
        item: dict[str, Any],
    ) -> None:
        """Recurse into one folder entry, replacing a stale local file first."""
        name = item["name"]
        sub_dir = dest / name
        if sub_dir.is_file():
            logging.info("OneDrive: replacing stale file %r with folder", name)
            sub_dir.unlink()
        logging.info("OneDrive: entering folder %r", name)
        self._sync_folder(session, drive_id, item["id"], token, sub_dir)

    def _download(self, session: requests.Session, url: str | None, dest_file: Path) -> None:
        """Stream a file to ``dest_file`` via a temp file, renamed on success.

        The temp file is created with O_EXCL so a pre-existing entry at the
        temp path (e.g. a symlink) is never followed, and the rename on
        success keeps a partially downloaded file from ever appearing at the
        final path: a download interrupted by a network drop or power loss
        leaves no truncated file that a later sync would skip as "existing".
        The byte count is verified against the response's Content-Length so a
        cleanly short response cannot be mistaken for a complete file.
        """
        if not url:
            raise RuntimeError(f"No download URL available for {dest_file.name}")
        tmp_file = dest_file.with_name(dest_file.name + ".part")
        try:
            fd = os.open(tmp_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            # A stale temp file: a hard process death (power loss, SIGKILL,
            # OOM) interrupts a download between the open and the rename,
            # which the in-process cleanup cannot undo.  Remove the stale
            # entry (a pre-planted symlink is removed, never followed) and
            # retry once; failing the whole sync here would self-perpetuate,
            # because the destructive cleanup runs only after the item loop.
            tmp_file.unlink(missing_ok=True)
            try:
                fd = os.open(tmp_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                raise RuntimeError(f"cannot create temp file {tmp_file} (path exists)") from None
        try:
            try:
                resp = session.get(url, stream=True, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
            except requests.HTTPError as e:
                # The HTTPError message embeds the download URL, which
                # carries a time-limited auth token; re-raise without it so
                # the token never reaches the logs or the settings panel.
                code = e.response.status_code if e.response is not None else "?"
                raise RuntimeError(f"download of {dest_file.name} failed: HTTP {code}") from e
            expected = -1
            length_hdr = resp.headers.get("Content-Length")
            if isinstance(length_hdr, str):
                try:
                    expected = int(length_hdr)
                except ValueError:
                    expected = -1
            written = 0
            with os.fdopen(fd, "wb") as f:
                for chunk in resp.iter_content(DOWNLOAD_CHUNK):
                    f.write(chunk)
                    written += len(chunk)
            if expected >= 0 and written != expected:
                raise RuntimeError(
                    f"Incomplete download of {dest_file.name}: {written} of {expected} bytes"
                )
            os.replace(tmp_file, dest_file)
        except BaseException:
            tmp_file.unlink(missing_ok=True)
            raise
