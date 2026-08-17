"""Unit tests for the providers package and album domain types."""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from PIL import Image as PilImage
from PIL.Image import Exif as PilExif

from piframe.album import Album
from piframe.album_provider import DirectoryReader
from piframe.config_store import ConfigStore
from piframe.exif import Exif, load_exif
from piframe.image import Image
from piframe.providers import (
    GooglePhotosConfig,
    GooglePhotosProvider,
    LocalProvider,
    OneDriveProvider,
    ProviderName,
)
from piframe.providers.local import LocalConfig
from piframe.providers.onedrive import OneDriveConfig, encode_url
from piframe.types import SyncStatus

# ---------------------------------------------------------------------------
# ProviderName
# ---------------------------------------------------------------------------


def test_provider_name_from_string_local() -> None:
    """from_string('local') returns ProviderName.LOCAL."""
    assert ProviderName.from_string("local") is ProviderName.LOCAL


def test_provider_name_from_string_onedrive() -> None:
    """from_string('onedrive') returns ProviderName.ONEDRIVE."""
    assert ProviderName.from_string("onedrive") is ProviderName.ONEDRIVE


def test_provider_name_from_string_google() -> None:
    """from_string('google') returns ProviderName.GOOGLE."""
    assert ProviderName.from_string("google") is ProviderName.GOOGLE


def test_provider_name_from_string_unknown_raises() -> None:
    """from_string('unknown') raises ValueError with valid options in message."""
    with pytest.raises(ValueError, match="Unknown sync provider"):
        ProviderName.from_string("unknown")


# ---------------------------------------------------------------------------
# DirectoryReader (legacy, retained for issue-43 exit criteria)
# ---------------------------------------------------------------------------


def test_directory_reader_nonexistent_dir(tmp_path: Path) -> None:
    """get_album() returns [] for nonexistent directory."""
    reader = DirectoryReader(tmp_path / "does-not-exist")
    assert reader.get_album() == []


def test_directory_reader_scans_files(tmp_path: Path) -> None:
    """get_album() returns sorted list of image files."""
    (tmp_path / "b.png").touch()
    (tmp_path / "a.jpg").touch()
    (tmp_path / "c.jpeg").touch()
    (tmp_path / "d.gif").touch()

    reader = DirectoryReader(tmp_path)
    result = reader.get_album()

    assert len(result) == 4
    names = [p.name for p in result]
    assert names == ["a.jpg", "b.png", "c.jpeg", "d.gif"]


def test_directory_reader_ignores_non_image(tmp_path: Path) -> None:
    """get_album() ignores files with non-image extensions."""
    (tmp_path / "photo.jpg").touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "report.pdf").touch()
    (tmp_path / "image.png").touch()

    reader = DirectoryReader(tmp_path)
    result = reader.get_album()

    assert len(result) == 2
    names = [p.name for p in result]
    assert names == ["image.png", "photo.jpg"]


# ---------------------------------------------------------------------------
# Album / Image / Exif
# ---------------------------------------------------------------------------


def test_album_empty_by_default() -> None:
    """A default album has no images."""
    album = Album()
    assert len(album) == 0
    assert list(iter(album)) == []
    assert album.images == ()


def test_album_from_images_supports_iteration_and_indexing() -> None:
    """Album supports iteration and indexed access (FR-2)."""
    a = Image(Path("/photos/a.jpg"))
    b = Image(Path("/photos/b.jpg"))
    album = Album.from_images([a, b])
    assert len(album) == 2
    assert list(iter(album)) == [a, b]
    assert album[0] is a
    assert album[1] is b


def test_album_defensive_copy_shares_immutable_tuple() -> None:
    """A defensive copy is a distinct object sharing the immutable tuple."""
    a = Image(Path("/photos/a.jpg"))
    original = Album.from_images([a])
    copy = Album.from_images(original.images)
    assert copy is not original
    assert copy.images == original.images
    assert len(copy) == 1


def test_image_exif_is_lazy_and_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """EXIF is loaded on first access and cached (NFR-6)."""
    calls: list[Path] = []

    def fake_load(path: Path) -> Exif:
        calls.append(path)
        return Exif(datetime=None, orientation=1)

    monkeypatch.setattr("piframe.image.load_exif", fake_load)
    img = Image(tmp_path / "a.jpg")
    assert calls == []
    assert img.exif is not None
    assert len(calls) == 1
    _ = img.exif
    assert len(calls) == 1


def test_load_exif_reads_datetime_and_orientation(tmp_path: Path) -> None:
    """load_exif reads capture datetime and orientation from a real JPEG.

    DateTimeOriginal lives in the Exif sub-IFD (0x8769), as in real
    camera files; orientation lives in the base IFD.
    """
    img = PilImage.new("RGB", (10, 10))
    exif = PilExif()
    exif[0x0112] = 6  # Orientation (base IFD)
    sub_ifd = exif.get_ifd(0x8769)  # Exif sub-IFD
    sub_ifd[0x9003] = "2024:05:01 12:30:00"  # DateTimeOriginal
    img.save(tmp_path / "photo.jpg", exif=exif)

    result = load_exif(tmp_path / "photo.jpg")
    assert result is not None
    assert result.orientation == 6
    assert result.datetime == datetime(2024, 5, 1, 12, 30, 0)


def test_load_exif_defaults_without_tags(tmp_path: Path) -> None:
    """A JPEG without EXIF tags yields default metadata, not an error."""
    PilImage.new("RGB", (10, 10)).save(tmp_path / "plain.jpg")
    result = load_exif(tmp_path / "plain.jpg")
    assert result is not None
    assert result.datetime is None
    assert result.orientation == 1


def test_load_exif_skips_oversized_file(tmp_path: Path) -> None:
    """Files above the size cap are not parsed: image decoders are a crash-class risk."""
    big = tmp_path / "big.jpg"
    with open(big, "wb") as f:
        f.seek(201 * 1024 * 1024)  # sparse: 201 MiB apparent size
        f.write(b"\0")
    assert load_exif(big) is None


def test_load_exif_missing_file_returns_none(tmp_path: Path) -> None:
    """load_exif never raises for a missing file (F-5)."""
    assert load_exif(tmp_path / "nope.jpg") is None


def test_load_exif_corrupt_file_returns_none(tmp_path: Path) -> None:
    """load_exif never raises for a corrupt file (F-5)."""
    (tmp_path / "corrupt.jpg").write_bytes(b"this is not an image")
    assert load_exif(tmp_path / "corrupt.jpg") is None


# ---------------------------------------------------------------------------
# OneDrive provider
# ---------------------------------------------------------------------------


def _mock_response(*, ok: bool = True, json_data: Any = None, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = ok
    resp.status_code = status_code
    resp.text = "" if ok else f"HTTP {status_code}"
    resp.json.return_value = json_data if json_data is not None else {}
    resp.raise_for_status.return_value = None
    return resp


def _onedrive_config(tmp_path: Path, cache_dir: Path) -> ConfigStore:
    p = tmp_path / "config.toml"
    p.write_text(
        "[sync]\n"
        'provider = "onedrive"\n'
        "[sync.onedrive]\n"
        'share_url = "https://1drv.ms/f/abc"\n'
        f'cache_dir = "{cache_dir}"\n'
    )
    return ConfigStore(p)


def _badger_posts(*, redeem: dict, fail_token: bool = False) -> list[MagicMock]:
    """The three Badger POST responses: token, validate, redeem."""
    token_resp = _mock_response(json_data={"token": "TOK"})
    if fail_token:
        token_resp.raise_for_status.side_effect = RuntimeError("network down")
    return [token_resp, _mock_response(ok=True), _mock_response(json_data=redeem)]


def _download_response(data: bytes = b"jpegdata") -> MagicMock:
    """A streaming download response yielding a single chunk."""
    resp = _mock_response()
    resp.iter_content.return_value = [data]
    return resp


def _mock_onedrive_session(
    monkeypatch: pytest.MonkeyPatch,
    *,
    posts: list[MagicMock],
    gets: list[MagicMock],
) -> MagicMock:
    """Patch the requests module used by the OneDrive provider.

    The provider creates one ``requests.Session`` per sync, so the mock
    exposes a ``Session`` factory whose instance carries the call
    sequences.  For a folder share the GET sequence is: one children
    listing per page and subfolder, then one download per new file.
    """
    mock_session = MagicMock()
    mock_session.post.side_effect = posts
    mock_session.get.side_effect = gets
    mock_requests = MagicMock()
    mock_requests.Session.return_value = mock_session
    # The provider's `except requests.HTTPError` clause needs a real
    # exception class, not a mock attribute.
    mock_requests.HTTPError = requests.exceptions.HTTPError
    monkeypatch.setattr("piframe.providers.onedrive.requests", mock_requests)
    return mock_session


def test_onedrive_config_reads_nested_keys(tmp_path: Path) -> None:
    """OneDriveConfig reads share_url, password, and cache_dir from [sync.onedrive]."""
    p = tmp_path / "config.toml"
    p.write_text(
        "[sync.onedrive]\n"
        'share_url = "https://1drv.ms/f/xyz"\n'
        'password = "pw"\n'
        f'cache_dir = "{tmp_path / "cache"}"\n'
    )
    cfg = OneDriveConfig(ConfigStore(p))
    assert cfg.share_url == "https://1drv.ms/f/xyz"
    assert cfg.password == "pw"
    assert cfg.cache_dir == tmp_path / "cache"


def test_onedrive_album_before_sync_returns_album_instance() -> None:
    """album() returns an Album instance (empty) before the first sync."""
    cfg = OneDriveConfig(ConfigStore(Path("/nonexistent.toml")))
    provider = OneDriveProvider(cfg)
    assert isinstance(provider.album(), Album)


def test_onedrive_status_and_album_before_sync() -> None:
    """Before the first sync the album is empty and status is at defaults."""
    cfg = OneDriveConfig(ConfigStore(Path("/nonexistent.toml")))
    provider = OneDriveProvider(cfg)
    assert len(provider.album()) == 0
    status = provider.status()
    assert status.photo_count == 0
    assert status.last_sync_time is None
    assert status.last_error is None
    assert status.in_progress is False


def test_onedrive_sync_happy_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Full sync: token, validate, redeem, list, download; album from cache."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "stale.jpg").write_bytes(b"stale")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "a.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/a.jpg",
        },
        {
            "id": "2",
            "name": "notes.txt",
            "file": {},
            "@content.downloadUrl": "https://dl/notes.txt",
        },
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[
            _mock_response(json_data={"value": listing}),
            _download_response(),
            _download_response(),
        ],
    )

    album = provider.sync()

    assert [img.path for img in album] == [cache_dir / "a.jpg"]
    assert (cache_dir / "a.jpg").read_bytes() == b"jpegdata"
    # Destructive cleanup removed the file no longer present remotely.
    assert not (cache_dir / "stale.jpg").exists()
    status = provider.status()
    assert status.photo_count == 1
    assert status.last_error is None
    assert status.in_progress is False
    assert status.last_sync_time is not None


def test_onedrive_sync_single_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A share pointing at a single file downloads it into the cache."""
    cache_dir = tmp_path / "cache"
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"name": "solo.jpg", "file": {}, "@content.downloadUrl": "https://dl/solo.jpg"}
        ),
        gets=[_download_response()],
    )

    album = provider.sync()

    assert [img.path for img in album] == [cache_dir / "solo.jpg"]
    assert (cache_dir / "solo.jpg").read_bytes() == b"jpegdata"


def test_onedrive_sync_missing_share_url_raises(tmp_path: Path) -> None:
    """A missing share URL fails the sync and is reported in status."""
    p = tmp_path / "config.toml"
    p.write_text('[sync]\nprovider = "onedrive"\n[sync.onedrive]\nshare_url = ""\n')
    provider = OneDriveProvider(OneDriveConfig(ConfigStore(p)))

    with pytest.raises(RuntimeError, match="share URL"):
        provider.sync()
    assert provider.status().last_error == "No OneDrive share URL configured"
    assert len(provider.album()) == 0


def test_onedrive_sync_network_error_keeps_previous_album(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed sync keeps the last known good album and records the error."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [{"name": "a.jpg", "file": {}, "@content.downloadUrl": "https://dl/a.jpg"}]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing}), _download_response()],
    )
    first_album = provider.sync()
    assert len(first_album) == 1

    # Second sync: the token request fails.
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"},
            fail_token=True,
        ),
        gets=[],
    )
    with pytest.raises(RuntimeError, match="network down"):
        provider.sync()

    assert provider.album().images == first_album.images
    status = provider.status()
    assert status.last_error == "network down"
    assert status.photo_count == 1  # unchanged from the last good sync


def test_onedrive_close_is_idempotent(tmp_path: Path) -> None:
    """close() can be called multiple times without error."""
    cfg = OneDriveConfig(ConfigStore(tmp_path / "nonexistent.toml"))
    provider = OneDriveProvider(cfg)
    provider.close()
    provider.close()


def test_onedrive_sync_folder_recurses_and_paginates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subfolder recursion, @odata.nextLink pagination, and stale-dir cleanup."""
    cache_dir = tmp_path / "cache"
    (cache_dir / "sub").mkdir(parents=True)
    (cache_dir / "sub" / "old.jpg").write_bytes(b"old")
    (cache_dir / "staledir").mkdir()
    (cache_dir / "staledir" / "junk.jpg").write_bytes(b"junk")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    sub_listing = [
        {"id": "3", "name": "c.jpg", "file": {}, "@content.downloadUrl": "https://dl/c.jpg"}
    ]
    page1 = [
        {"id": "2", "name": "sub", "folder": {}},
        {"id": "5", "name": "top.jpg", "file": {}, "@content.downloadUrl": "https://dl/top.jpg"},
    ]
    page2 = [{"id": "4", "name": "b.jpg", "file": {}, "@content.downloadUrl": "https://dl/b.jpg"}]
    # GET sequence: root page 1, sub children, c.jpg, top.jpg, root page 2, b.jpg
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[
            _mock_response(json_data={"value": page1, "@odata.nextLink": "https://api/page2"}),
            _mock_response(json_data={"value": sub_listing}),
            _download_response(),
            _download_response(),
            _mock_response(json_data={"value": page2}),
            _download_response(),
        ],
    )

    album = provider.sync()

    assert (cache_dir / "sub" / "c.jpg").read_bytes() == b"jpegdata"
    assert (cache_dir / "top.jpg").read_bytes() == b"jpegdata"
    assert (cache_dir / "b.jpg").read_bytes() == b"jpegdata"
    # Stale content in a surviving folder and a stale top-level dir are removed.
    assert not (cache_dir / "sub" / "old.jpg").exists()
    assert not (cache_dir / "staledir").exists()
    assert [img.path for img in album] == [
        cache_dir / "b.jpg",
        cache_dir / "sub" / "c.jpg",
        cache_dir / "top.jpg",
    ]


def test_onedrive_sync_skips_existing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-sync does not re-download files that already exist locally."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "a.jpg").write_bytes(b"original")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {"id": "1", "name": "a.jpg", "file": {}, "@content.downloadUrl": "https://dl/a.jpg"}
    ]
    session = _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing})],
    )

    album = provider.sync()

    assert (cache_dir / "a.jpg").read_bytes() == b"original"  # untouched
    assert session.get.call_count == 1  # listing only, no download
    assert [img.path for img in album] == [cache_dir / "a.jpg"]


def test_onedrive_sync_item_lookup_when_download_url_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file item without @content.downloadUrl is looked up by id first."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [{"id": "77", "name": "a.jpg", "file": {}}]  # no download URL
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[
            _mock_response(json_data={"value": listing}),
            _mock_response(json_data={"@content.downloadUrl": "https://dl/a.jpg"}),
            _download_response(),
        ],
    )

    album = provider.sync()

    assert (cache_dir / "a.jpg").read_bytes() == b"jpegdata"
    assert [img.path for img in album] == [cache_dir / "a.jpg"]


def test_onedrive_sync_rejects_unsafe_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Remote names with path separators or '..' are skipped (no traversal)."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "../../evil.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/evil.jpg",
        },
        {"id": "2", "name": "ok.jpg", "file": {}, "@content.downloadUrl": "https://dl/ok.jpg"},
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[
            _mock_response(json_data={"value": listing}),
            _download_response(),  # only ok.jpg is downloaded
        ],
    )

    album = provider.sync()

    assert (cache_dir / "ok.jpg").read_bytes() == b"jpegdata"
    assert not (tmp_path / "evil.jpg").exists()
    assert not (tmp_path.parent / "evil.jpg").exists()
    assert [img.path for img in album] == [cache_dir / "ok.jpg"]


def test_onedrive_sync_type_change_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Local entries whose type no longer matches the remote are replaced."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "wasdir.jpg").mkdir()
    (cache_dir / "wasdir.jpg" / "inner.jpg").write_bytes(b"inner")
    (cache_dir / "wasfile.jpg").write_bytes(b"old")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "wasdir.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/wasdir.jpg",
        },
        {"id": "2", "name": "wasfile.jpg", "folder": {}},
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[
            _mock_response(json_data={"value": listing}),
            _download_response(),  # wasdir.jpg: dir replaced by file
            _mock_response(json_data={"value": []}),  # wasfile.jpg: now an empty folder
        ],
    )

    album = provider.sync()

    assert (cache_dir / "wasdir.jpg").is_file()
    assert (cache_dir / "wasdir.jpg").read_bytes() == b"jpegdata"
    assert (cache_dir / "wasfile.jpg").is_dir()
    assert [img.path for img in album] == [cache_dir / "wasdir.jpg"]


def test_onedrive_download_is_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed download leaves no partial file at the final path."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {"id": "1", "name": "a.jpg", "file": {}, "@content.downloadUrl": "https://dl/a.jpg"}
    ]
    failed_dl = _mock_response()
    failed_dl.raise_for_status.side_effect = RuntimeError("download failed")
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing}), failed_dl],
    )

    with pytest.raises(RuntimeError, match="download failed"):
        provider.sync()

    assert not (cache_dir / "a.jpg").exists()  # no partial file at the final path
    leftovers = [p for p in cache_dir.iterdir() if p.name.endswith(".part")]
    assert leftovers == []  # temp file cleaned up
    assert provider.status().last_error == "download failed"


def test_onedrive_sync_single_file_cleans_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A renamed remote file leaves no stale local copy after sync."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "old-name.jpg").write_bytes(b"old")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={
                "name": "new-name.jpg",
                "file": {},
                "@content.downloadUrl": "https://dl/new-name.jpg",
            }
        ),
        gets=[_download_response()],
    )

    album = provider.sync()

    assert (cache_dir / "new-name.jpg").read_bytes() == b"jpegdata"
    assert not (cache_dir / "old-name.jpg").exists()
    assert [img.path for img in album] == [cache_dir / "new-name.jpg"]


def test_onedrive_download_short_response_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A response that ends short of Content-Length is not accepted as complete."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {"id": "1", "name": "a.jpg", "file": {}, "@content.downloadUrl": "https://dl/a.jpg"}
    ]
    short_dl = _mock_response()
    short_dl.headers = {"Content-Length": "100"}
    short_dl.iter_content.return_value = [b"short"]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing}), short_dl],
    )

    with pytest.raises(RuntimeError, match="Incomplete download"):
        provider.sync()

    assert not (cache_dir / "a.jpg").exists()
    assert [p for p in cache_dir.iterdir() if p.name.endswith(".part")] == []


def test_onedrive_download_http_error_sanitized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed download never leaks the auth token from the URL into the error."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "a.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/a.jpg?token=SECRET123",
        }
    ]
    dl_resp = _mock_response()
    fake_http_resp = MagicMock(status_code=404)
    dl_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "404 Client Error: Not Found for url: https://dl/a.jpg?token=SECRET123",
        response=fake_http_resp,
    )
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing}), dl_resp],
    )

    with pytest.raises(RuntimeError, match="HTTP 404"):
        provider.sync()

    assert "SECRET123" not in (provider.status().last_error or "")
    assert not (cache_dir / "a.jpg").exists()


def test_onedrive_download_temp_path_symlink_not_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pre-planted symlink at the temp path is removed, never followed."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"precious")
    (cache_dir / "a.jpg.part").symlink_to(outside)
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "a.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/a.jpg",
        }
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing}), _download_response()],
    )

    album = provider.sync()

    # The pre-planted symlink is removed, never followed: the outside file is
    # untouched and the download completes into a fresh regular file.
    assert outside.read_bytes() == b"precious"
    assert (cache_dir / "a.jpg").read_bytes() == b"jpegdata"
    assert not (cache_dir / "a.jpg.part").exists()
    assert [img.path for img in album] == [cache_dir / "a.jpg"]


def test_onedrive_download_stale_part_file_self_heals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale .part file from an interrupted download is removed and the download retried.

    A hard process death (power loss, SIGKILL, OOM) interrupts a download
    between the temp-file open and the rename; the in-process cleanup cannot
    run, so the next sync must recover instead of failing forever.
    """
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "a.jpg.part").write_bytes(b"partial garbage")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "a.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/a.jpg",
        }
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing}), _download_response()],
    )

    album = provider.sync()

    assert (cache_dir / "a.jpg").read_bytes() == b"jpegdata"
    assert not (cache_dir / "a.jpg.part").exists()
    assert [img.path for img in album] == [cache_dir / "a.jpg"]


def test_onedrive_sync_newline_name_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A remote item name containing a newline is rejected: no file, no forged log line."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [
        {
            "id": "1",
            "name": "x\n2024-01-01 00:00:00 [INFO] forged.jpg",
            "file": {},
            "@content.downloadUrl": "https://dl/forged.jpg",
        }
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing})],
    )

    album = provider.sync()

    # The item was skipped: nothing was created in the cache dir.
    assert [p.name for p in cache_dir.iterdir()] == []
    assert [img.path for img in album] == []


def test_onedrive_sync_dot_name_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A remote item named '.' is skipped: no recursion into the parent directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "keep.jpg").write_bytes(b"keep")
    # A file outside the cache dir: if the '.' item were followed as a
    # folder, the provider would recurse into the parent and clean it up.
    sibling = tmp_path / "sibling.jpg"
    sibling.write_bytes(b"sibling")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [{"id": "1", "name": ".", "folder": {}}]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing})],
    )

    album = provider.sync()

    # The '.' item was skipped: the sibling outside the cache dir survives.
    assert sibling.read_bytes() == b"sibling"
    # Normal destructive cleanup still applies inside the cache dir.
    assert not (cache_dir / "keep.jpg").exists()
    assert [img.path for img in album] == []


def test_onedrive_sync_after_close_raises(tmp_path: Path) -> None:
    """sync() refuses to run once the provider is closed."""
    cfg = OneDriveConfig(ConfigStore(tmp_path / "nonexistent.toml"))
    provider = OneDriveProvider(cfg)
    provider.close()
    with pytest.raises(RuntimeError, match="closed"):
        provider.sync()


def test_onedrive_sync_bad_password_fails_and_keeps_album(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed password validation fails the sync and keeps the previous album."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "a.jpg").write_bytes(b"old")
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    # First sync succeeds (a.jpg already cached, so no download).
    listing = [
        {"id": "1", "name": "a.jpg", "file": {}, "@content.downloadUrl": "https://dl/a.jpg"}
    ]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[_mock_response(json_data={"value": listing})],
    )
    first_album = provider.sync()
    assert len(first_album) == 1

    # Second sync: password validation fails (403).
    bad_validate = _mock_response(ok=False, status_code=403)
    bad_validate.raise_for_status.side_effect = RuntimeError("403 Client Error")
    _mock_onedrive_session(
        monkeypatch,
        posts=[
            _mock_response(json_data={"token": "TOK"}),
            bad_validate,
        ],
        gets=[],
    )
    with pytest.raises(RuntimeError, match="403"):
        provider.sync()

    assert "403" in (provider.status().last_error or "")
    assert provider.album().images == first_album.images


def test_onedrive_sync_item_lookup_without_url_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing download URL, even after the item lookup, fails the sync cleanly."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cfg = _onedrive_config(tmp_path, cache_dir)
    provider = OneDriveProvider(OneDriveConfig(cfg))

    listing = [{"id": "77", "name": "a.jpg", "file": {}}]
    _mock_onedrive_session(
        monkeypatch,
        posts=_badger_posts(
            redeem={"id": "F1", "parentReference": {"driveId": "D1"}, "name": "photos"}
        ),
        gets=[
            _mock_response(json_data={"value": listing}),
            _mock_response(json_data={}),  # item lookup: no @content.downloadUrl
        ],
    )
    with pytest.raises(RuntimeError, match="No download URL"):
        provider.sync()
    assert not (cache_dir / "a.jpg").exists()


def test_close_waits_for_in_flight_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    """close() blocks while a sync is in flight, then releases when it finishes."""
    from piframe.providers import base as base_mod
    from piframe.providers.base import BaseAlbumProvider

    class SlowProvider(BaseAlbumProvider):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def _do_sync(self) -> Album:
            self.started.set()
            self.release.wait(10)
            return Album()

    monkeypatch.setattr(base_mod, "CLOSE_SYNC_TIMEOUT", 5.0)
    provider = SlowProvider()
    sync_thread = threading.Thread(target=provider.sync, daemon=True)
    sync_thread.start()
    assert provider.started.wait(5)

    close_thread = threading.Thread(target=provider.close, daemon=True)
    close_thread.start()
    close_thread.join(2.0)
    assert close_thread.is_alive()  # still blocked: the sync is in flight
    provider.release.set()
    sync_thread.join(5)
    assert not sync_thread.is_alive()
    close_thread.join(5)
    assert not close_thread.is_alive()
    assert provider._closed


def test_status_and_album_returns_are_isolated_copies(tmp_path: Path) -> None:
    """Mutating a returned status never touches the provider; a held album stays a snapshot."""
    cfg = OneDriveConfig(ConfigStore(tmp_path / "nonexistent.toml"))
    provider = OneDriveProvider(cfg)

    status = provider.status()
    status.photo_count = 999
    status.last_error = "mutated"
    assert provider.status().photo_count == 0
    assert provider.status().last_error is None

    before = provider.album()
    provider._album = Album.from_images([Image(tmp_path / "new.jpg")])  # simulate a sync swap
    after = provider.album()
    assert before.images == ()
    assert [img.path for img in after] == [tmp_path / "new.jpg"]


def test_encode_url() -> None:
    """encode_url base64-encodes with the Badger alphabet."""
    assert encode_url("https://1drv.ms/f/abc") == "aHR0cHM6Ly8xZHJ2Lm1zL2YvYWJj"


# ---------------------------------------------------------------------------
# Local provider
# ---------------------------------------------------------------------------


def _local_config(tmp_path: Path, source_dir: Path) -> ConfigStore:
    p = tmp_path / "config.toml"
    p.write_text(f'[sync]\nprovider = "local"\n[sync.local]\nsource_dir = "{source_dir}"\n')
    return ConfigStore(p)


def test_local_config_reads_source_dir(tmp_path: Path) -> None:
    """LocalConfig reads source_dir from [sync.local]."""
    cfg = LocalConfig(_local_config(tmp_path, tmp_path / "photos"))
    assert cfg.source_dir == tmp_path / "photos"


def test_local_sync_returns_direct_references(tmp_path: Path) -> None:
    """LocalProvider returns direct references to source files (no copy)."""
    source = tmp_path / "photos"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"1")
    (source / "b.png").write_bytes(b"2")
    (source / "notes.txt").write_bytes(b"3")
    # A subdirectory with an image inside: the scan is non-recursive.
    (source / "sub").mkdir()
    (source / "sub" / "c.jpg").write_bytes(b"4")
    provider = LocalProvider(LocalConfig(_local_config(tmp_path, source)))

    album = provider.sync()

    assert [img.path for img in album] == [source / "a.jpg", source / "b.png"]
    # No copying: the files live in the source directory, unmodified.
    assert (source / "a.jpg").read_bytes() == b"1"
    assert (source / "b.png").read_bytes() == b"2"
    assert (source / "notes.txt").read_bytes() == b"3"
    assert (source / "sub" / "c.jpg").read_bytes() == b"4"


def test_local_sync_no_cleanup_of_source(tmp_path: Path) -> None:
    """The provider never deletes source files (the user controls them)."""
    source = tmp_path / "photos"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"1")
    provider = LocalProvider(LocalConfig(_local_config(tmp_path, source)))

    provider.sync()
    provider.sync()

    assert (source / "a.jpg").exists()


def test_local_sync_missing_source_dir(tmp_path: Path) -> None:
    """A missing source directory yields an empty album, not an error."""
    provider = LocalProvider(LocalConfig(_local_config(tmp_path, tmp_path / "nope")))

    album = provider.sync()

    assert len(album) == 0
    status = provider.status()
    assert status.photo_count == 0
    assert status.last_error is None


def test_local_status_photo_count(tmp_path: Path) -> None:
    """status() reports the number of images in the source directory."""
    source = tmp_path / "photos"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"1")
    (source / "b.jpeg").write_bytes(b"2")
    provider = LocalProvider(LocalConfig(_local_config(tmp_path, source)))

    provider.sync()

    assert provider.status().photo_count == 2


# ---------------------------------------------------------------------------
# Google Photos stub
# ---------------------------------------------------------------------------


def _google_provider() -> GooglePhotosProvider:
    return GooglePhotosProvider(GooglePhotosConfig(ConfigStore(Path("/nonexistent.toml"))))


def test_google_sync_returns_empty_album_and_error() -> None:
    """sync() returns an empty album and reports not-yet-implemented (FR-5)."""
    provider = _google_provider()

    album = provider.sync()

    assert len(album) == 0
    status = provider.status()
    assert status.last_error == "Google Photos provider is not yet implemented"
    assert status.photo_count == 0
    assert status.in_progress is False
    assert status.last_sync_time is not None


def test_google_album_empty_before_sync() -> None:
    """album() returns an empty album before any sync."""
    assert len(_google_provider().album()) == 0


def test_google_status_never_raises() -> None:
    """status() works before and after sync."""
    provider = _google_provider()
    assert isinstance(provider.status(), SyncStatus)
    provider.sync()
    assert isinstance(provider.status(), SyncStatus)


def test_google_close_noop() -> None:
    """close() is a safe no-op for the stub."""
    provider = _google_provider()
    provider.close()
    provider.close()
