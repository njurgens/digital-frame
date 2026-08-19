"""TOML-based configuration store with typed section accessors."""

from __future__ import annotations

import logging
import os
import shutil
import time
import tomllib
from copy import deepcopy
from datetime import time as dtime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tomli_w

if TYPE_CHECKING:
    from piframe.providers import ProviderName

#: Environment variable prefix for config overrides.  The remainder of the
#: variable name is a ``__``-separated, upper-case config path, e.g.
#: ``PIFRAME_SYNC__ONEDRIVE__SHARE_URL`` overrides ``sync.onedrive.share_url``.
_ENV_PREFIX = "PIFRAME_"
_ENV_SEP = "__"

#: Keys the app must never persist: their on-disk values always win on
#: flush, so env-var-injected secrets and user-edited values stay safe.
_PROTECTED: frozenset[tuple[str, ...]] = frozenset(
    {
        ("sync", "provider"),
        ("sync", "onedrive", "share_url"),
        ("sync", "onedrive", "password"),
    }
)

#: Flat ``[sync]`` keys from the pre-provider config format.  They are no
#: longer read; loading a file that still carries them logs a migration hint.
_LEGACY_SYNC_KEYS = ("share_url", "password", "output_dir", "cache_dir")

_DEFAULTS = {
    "app": {"mock_wifi": False},
    "ipc": {"enabled": False},
    "slideshow": {"interval": 30.0, "fit_mode": "fit", "shuffle": True, "transition": "crossfade"},
    "display": {"brightness": 72, "show_clock": True, "timezone_auto": True},
    "sleep": {"enabled": False, "sleep_time": "22:00", "wake_time": "07:00"},
    "sync": {
        "provider": "local",
        "interval_minutes": 60,
        "onedrive": {
            "share_url": "",
            "password": "",
            "cache_dir": "~/.cache/piframe/onedrive",
        },
        "local": {
            "source_dir": "~/Pictures/slideshow",
        },
        "google": {},
    },
    "system": {"timezone": "America/Los_Angeles"},
    "update": {"repo": "njurgens/digital-frame"},
}

_CLAMP = {
    ("slideshow", "interval"): (1.0, 3600.0),
    ("display", "brightness"): (0, 100),
    ("sync", "interval_minutes"): (1, 1440),
}


def _get_path(data: dict, path: tuple[str, ...]) -> object | None:
    """Return the value at *path* in nested dicts, or None if absent."""
    node: object = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _set_path(data: dict, path: tuple[str, ...], value: object) -> None:
    """Set the value at *path* in nested dicts, creating missing tables."""
    node: dict = data
    for key in path[:-1]:
        child = node.setdefault(key, {})
        if not isinstance(child, dict):
            return
        node = child
    node[path[-1]] = value


def _remove_path(data: dict, path: tuple[str, ...]) -> None:
    """Remove the value at *path* from nested dicts, if present."""
    node: dict = data
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            return
        node = child
    node.pop(path[-1], None)


def _env_name_for(path: tuple[str, ...]) -> str:
    """Environment variable name that overrides the config path."""
    return _ENV_PREFIX + _ENV_SEP.join(part.upper() for part in path)


class _AppCfg:
    """App-level configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def mock_wifi(self) -> bool:
        return bool(self._d.get("mock_wifi", False))


class _IpcCfg:
    """IPC API configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def enabled(self) -> bool:
        return bool(self._d.get("enabled", False))


class _SlideshowCfg:
    """Slideshow configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def interval(self) -> float:
        return float(self._d.get("interval", 30.0))

    @property
    def fit_mode(self) -> str:
        m = str(self._d.get("fit_mode", "fit"))
        return m if m in {"fit", "fill"} else "fit"

    @property
    def shuffle(self) -> bool:
        return bool(self._d.get("shuffle", True))

    @property
    def transition(self) -> str:
        return str(self._d.get("transition", "crossfade"))


class _DisplayCfg:
    """Display configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def brightness(self) -> int:
        return int(self._d.get("brightness", 72))

    @property
    def show_clock(self) -> bool:
        return bool(self._d.get("show_clock", True))

    @property
    def timezone_auto(self) -> bool:
        return bool(self._d.get("timezone_auto", True))


class _SleepCfg:
    """Sleep schedule configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def enabled(self) -> bool:
        return bool(self._d.get("enabled", False))

    @property
    def sleep_time(self) -> str:
        return str(self._d.get("sleep_time", "22:00"))

    @property
    def wake_time(self) -> str:
        return str(self._d.get("wake_time", "07:00"))

    @property
    def sleep_time_parsed(self) -> dtime:
        h, m = self.sleep_time.split(":")
        return dtime(int(h), int(m))

    @property
    def wake_time_parsed(self) -> dtime:
        h, m = self.wake_time.split(":")
        return dtime(int(h), int(m))


class _SyncCfg:
    """Photo sync configuration values.

    Only the shared sync settings live here; provider-specific keys are
    read through :meth:`ConfigStore.read_nested` by the provider config
    wrapper classes.
    """

    def __init__(self, data: dict):
        self._d = data

    @property
    def provider(self) -> ProviderName:
        # Imported lazily: a module-level import of piframe.providers
        # would create an import cycle with this module's type hints.
        from piframe.providers import ProviderName as _ProviderName

        return _ProviderName.from_string(str(self._d.get("provider", "local")))

    @property
    def interval_minutes(self) -> int:
        return int(self._d.get("interval_minutes", 60))


class _SystemCfg:
    """System configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def timezone(self) -> str:
        return str(self._d.get("timezone", "America/Los_Angeles"))


class _UpdateCfg:
    """Update configuration values."""

    def __init__(self, data: dict):
        self._d = data

    @property
    def repo(self) -> str:
        return str(self._d.get("repo", "njurgens/digital-frame"))


class ConfigStore:
    """TOML-based configuration store with typed section accessors.

    Reads from disk on init, merges user overrides, protects secrets,
    and flushes changes back to disk on a delay.
    """

    def __init__(self, path: str | Path) -> None:
        """Initialise the config store from a TOML file.

        Args:
            path: Path to the TOML configuration file.

        """
        self._path = Path(path)
        self._data = deepcopy(_DEFAULTS)
        self._dirty_at: float | None = None
        # Protected paths whose in-memory values came from a legacy-file
        # migration: the running provider needs them, so a flush must not
        # revert them just because the (pre-migration) file lacks them.
        self._migrated_paths: set[tuple[str, ...]] = set()
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with self._path.open("rb") as f:
                    loaded = tomllib.load(f)
                migrated = self._migrate_legacy_sync(loaded)
                self._merge(loaded)
                if not migrated:
                    self._warn_legacy_sync_keys(loaded)
            except Exception as e:
                logging.warning("config load failed (%s), backing up and using defaults", e)
                backup = self._path.with_suffix(".bak")
                try:
                    shutil.copy2(self._path, backup)
                except OSError:
                    pass
                self._data = deepcopy(_DEFAULTS)
                self._migrated_paths = set()
        self._apply_env_overrides()

    def _migrate_legacy_sync(self, loaded: dict) -> bool:
        """One-time migration of a pre-provider config file (in memory).

        A legacy file has flat ``[sync]`` keys and no ``sync.provider``.
        Two cases:

        * a legacy ``share_url`` is present: the OneDrive settings move to
          the new layout — ``provider`` becomes ``"onedrive"`` and the old
          ``output_dir`` (where the photos live) becomes the provider's
          ``cache_dir`` so existing downloads are reused instead of
          re-downloaded.  The directory becomes provider-managed: files not
          present remotely are deleted on sync (the old folder-share sync
          already did this; single-file shares gain it).
        * no ``share_url`` but a legacy ``output_dir`` is: the local
          provider's ``source_dir`` is seeded from it, so a local-directory
          user keeps seeing their photos.

        The legacy keys stay in the file (the writer preserves them), so a
        rollback to the old code still works, and the migration re-applies on
        every load until the file is in the new format.  Returns True when a
        migration happened.
        """
        sync = loaded.get("sync")
        if not isinstance(sync, dict) or "provider" in sync:
            return False
        share_url = str(sync.get("share_url") or "").strip()
        if not share_url:
            # No OneDrive share to migrate, but a custom photo directory is
            # still worth preserving: point the local provider at the legacy
            # output_dir, so an existing local-directory user keeps seeing
            # their photos after the upgrade.
            output_dir = str(sync.get("output_dir") or "").strip()
            if not output_dir:
                return False
            local = sync.get("local")
            if not isinstance(local, dict):
                local = {}
            local.setdefault("source_dir", output_dir)
            sync["local"] = local
            logging.info(
                "config: pointed the local provider at the legacy output_dir %r", output_dir
            )
            return True
        onedrive = sync.get("onedrive")
        if not isinstance(onedrive, dict):
            onedrive = {}
        onedrive["share_url"] = share_url
        password = str(sync.get("password") or "").strip()
        if password:
            onedrive["password"] = password
        output_dir = str(sync.get("output_dir") or "").strip()
        if output_dir:
            onedrive["cache_dir"] = output_dir
        sync["onedrive"] = onedrive
        sync["provider"] = "onedrive"
        self._migrated_paths = {("sync", "provider"), ("sync", "onedrive", "share_url")}
        if password:
            self._migrated_paths.add(("sync", "onedrive", "password"))
        logging.info(
            "config: migrated legacy OneDrive [sync] keys to [sync.onedrive]; "
            "the cache dir is now provider-managed: files not present remotely are deleted on sync"
        )
        return True

    def _warn_legacy_sync_keys(self, loaded: dict) -> None:
        """Log a note for a config file that still carries legacy ``[sync]`` keys.

        Two cases:  a file with a ``provider`` key and leftover legacy keys
        has already been migrated (or hand-migrated) — the keys are retained
        for rollback and are simply noted.  A file without a ``provider`` key
        but with legacy keys that were not auto-migrated (no legacy
        ``share_url``) needs user action, so it gets a warning.
        """
        sync = loaded.get("sync")
        if not isinstance(sync, dict):
            return
        found = [key for key in _LEGACY_SYNC_KEYS if key in sync]
        if not found:
            return
        if "provider" in sync:
            logging.info(
                "config: legacy [sync] keys %s are retained for rollback; delete them manually",
                found,
            )
        else:
            logging.warning(
                "config: legacy [sync] keys %s are no longer read; "
                "set sync.provider and move them to [sync.onedrive]",
                found,
            )

    def _merge(self, loaded: dict) -> None:
        self._deep_merge(self._data, loaded)

    def _deep_merge(self, base: dict, override: dict, path: tuple[str, ...] = ()) -> None:
        """Merge *override* into *base*, recursing into nested tables.

        File values override defaults key by key; keys absent from the
        file keep their default values (including nested provider tables).
        """
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_merge(base[key], value, (*path, key))
            else:
                base[key] = self._clamp_path((*path, key), value)

    def _clamp(self, section: str, key: str, value: float | str | bool) -> float | str | bool:
        bounds = _CLAMP.get((section, key))
        if bounds is None or not isinstance(value, (int, float)) or isinstance(value, bool):
            return value
        lo, hi = bounds
        return type(value)(max(lo, min(hi, value)))

    def _clamp_path(self, path: tuple[str, ...], value: object) -> object:
        """Clamp a value at a nested path if bounds are defined for it."""
        if len(path) >= 2:
            bounds = _CLAMP.get((path[0], path[1]))
            if (
                bounds is not None
                and isinstance(value, (int, float))
                and not isinstance(value, bool)
            ):
                lo, hi = bounds
                return type(value)(max(lo, min(hi, value)))
        return value

    def tick(self, now: float) -> None:
        """Check if enough time has passed to flush pending changes."""
        if self._dirty_at is not None and now - self._dirty_at >= 0.5:
            self.flush_now()

    def flush_now(self) -> None:
        """Write the current configuration to disk immediately.

        Protected keys are never persisted from memory: the on-disk value
        always wins in the written file (or the key is omitted when absent
        from disk), so env-var-injected secrets are never written.  The
        in-memory value follows the file unless an env var owns the key, in
        which case the env value stays in memory for the running app.

        If the on-disk file cannot be read (e.g. a hand-edit introduced a
        TOML syntax error while the app runs), the in-memory values are
        written: treating an unreadable file as "all keys absent" would wipe
        the user's credentials from the file.  Env-var-owned protected values
        are never written in any case — a missing or unreadable file cannot
        authorise persisting a secret.

        Values the migration moved from the file's own legacy keys are the one
        exception to "never persisted from memory": they are the file's own
        data, so a flush converges the file to the new layout (provider key
        and onedrive sub-section) while the legacy keys are kept for rollback.
        """
        disk: dict | None = None
        if self._path.exists():
            try:
                with self._path.open("rb") as f:
                    disk = tomllib.load(f)
            except Exception as e:
                logging.warning(
                    "config flush: could not read %s (%s); keeping in-memory protected values",
                    self._path,
                    e,
                )
        to_write = deepcopy(self._data)
        if disk is not None:
            for path in _PROTECTED:
                disk_val = _get_path(disk, path)
                env_owned = os.environ.get(_env_name_for(path)) is not None
                if disk_val is None:
                    if path in self._migrated_paths and not env_owned:
                        # The value came from this file's own legacy keys (via
                        # the migration): writing it converges the file to the
                        # new format without ever persisting a foreign secret.
                        _set_path(to_write, path, _get_path(self._data, path))
                    else:
                        _remove_path(to_write, path)
                else:
                    _set_path(to_write, path, disk_val)
                if env_owned:
                    continue
                if path == ("sync", "provider"):
                    # The in-memory value reflects the running provider; the
                    # file's value takes effect on the next load, not
                    # mid-session.
                    continue
                if disk_val is None:
                    if path in self._migrated_paths:
                        # The running provider needs this value; keep it in
                        # memory (the file keeps the legacy keys meanwhile).
                        continue
                    _remove_path(self._data, path)
                else:
                    _set_path(self._data, path, disk_val)
        else:
            # No on-disk value exists (file missing or unreadable): the
            # in-memory values are written as-is, except env-var-owned
            # secrets, which must never be materialised into the file.
            for path in _PROTECTED:
                if os.environ.get(_env_name_for(path)) is not None:
                    _remove_path(to_write, path)
        self._write_toml(to_write)
        # A failed write (non-serializable value, full or read-only disk)
        # drops the pending flush instead of retrying forever: the in-memory
        # state stays live for the running app, and the warning above tells
        # the operator what to fix.
        self._dirty_at = None

    def set(self, section: str, key: str, value: float | str | bool) -> None:
        """Set a configuration value and schedule a delayed flush."""
        value = self._clamp(section, key, value)
        self._data.setdefault(section, {})[key] = value
        if self._dirty_at is None:
            self._dirty_at = time.monotonic()

    def read_nested(self, *keys: str, default: Any = None) -> Any:
        """Read a value at a nested config path.

        Args:
            *keys: Path components, e.g. ``"sync", "onedrive", "share_url"``.
            default: Value returned when any path component is missing.

        Returns:
            The stored value, or *default*.

        """
        value = _get_path(self._data, keys)
        return default if value is None else value

    def _apply_env_overrides(self) -> None:
        """Overlay ``PIFRAME_``-prefixed environment variables onto the config.

        The remainder of a variable name is a ``__``-separated, upper-case
        config path (e.g. ``PIFRAME_SYNC__ONEDRIVE__SHARE_URL``).  Values
        are coerced to the type of the existing value.  Unknown paths are
        silently ignored (FR-10).
        """
        for name, value in os.environ.items():
            if not name.startswith(_ENV_PREFIX):
                continue
            parts = [part.lower() for part in name[len(_ENV_PREFIX) :].split(_ENV_SEP)]
            if len(parts) < 2 or any(not part for part in parts):
                continue
            self._set_nested(parts, value)

    def _set_nested(self, path: list[str], value: str) -> None:
        node: object = self._data
        for key in path[:-1]:
            if not isinstance(node, dict):
                return
            child = node.get(key)
            if not isinstance(child, dict):
                return
            node = child
        if not isinstance(node, dict) or path[-1] not in node:
            return
        if isinstance(node[path[-1]], dict):
            return
        node[path[-1]] = self._clamp_path(tuple(path), self._coerce(value, node[path[-1]]))

    @staticmethod
    def _coerce(value: str, existing: object) -> object:
        """Coerce an env-var string to the type of *existing*."""
        if isinstance(existing, bool):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(existing, int):
            try:
                return int(value)
            except ValueError:
                return existing
        if isinstance(existing, float):
            try:
                return float(value)
            except ValueError:
                return existing
        return value

    def _write_toml(self, data: dict) -> None:
        tmp = self._path.with_name(self._path.name + ".tmp")
        try:
            text = tomli_w.dumps(data)
            # The file may hold credentials: create the temp file 0600 and
            # rename it into place on success.  A mid-write failure (disk
            # full, read-only) leaves the previous file intact, and the
            # config is never world-readable, not even for an instant.
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(text)
            os.replace(tmp, self._path)
        except (ValueError, TypeError, OSError) as e:
            # tomli-w rejects values tomllib accepts (e.g. TOML dates a
            # user may have added to the file), and the disk can be full or
            # read-only: a failed write must not take the app down.  The
            # in-memory state is kept for the running app.
            tmp.unlink(missing_ok=True)
            logging.warning("config write to %s failed: %s", self._path, e)

    def _read_raw(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    @property
    def app(self) -> _AppCfg:
        """App-level configuration accessor."""
        return _AppCfg(self._data.setdefault("app", {}))

    @property
    def ipc(self) -> _IpcCfg:
        """IPC API configuration accessor."""
        return _IpcCfg(self._data.setdefault("ipc", {}))

    @property
    def slideshow(self) -> _SlideshowCfg:
        """Slideshow configuration accessor."""
        return _SlideshowCfg(self._data.setdefault("slideshow", {}))

    @property
    def display(self) -> _DisplayCfg:
        """Display configuration accessor."""
        return _DisplayCfg(self._data.setdefault("display", {}))

    @property
    def sleep(self) -> _SleepCfg:
        """Sleep schedule configuration accessor."""
        return _SleepCfg(self._data.setdefault("sleep", {}))

    @property
    def sync(self) -> _SyncCfg:
        """Photo sync configuration accessor."""
        return _SyncCfg(self._data.setdefault("sync", {}))

    @property
    def system(self) -> _SystemCfg:
        """System configuration accessor."""
        return _SystemCfg(self._data.setdefault("system", {}))

    @property
    def update(self) -> _UpdateCfg:
        """Update configuration accessor."""
        return _UpdateCfg(self._data.setdefault("update", {}))
