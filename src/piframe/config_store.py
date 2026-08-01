from __future__ import annotations

import logging
import shutil
import time
import tomllib
from copy import deepcopy
from datetime import time as dtime
from pathlib import Path

_PROTECTED = {
    ("sync", "share_url"),
    ("sync", "password"),
    ("sync", "output_dir"),
    ("sync", "cache_dir"),
}

_DEFAULTS = {
    "slideshow": {"interval": 30.0, "fit_mode": "fit", "shuffle": True, "transition": "crossfade"},
    "display": {"brightness": 72, "show_clock": True, "timezone_auto": True},
    "sleep": {"enabled": False, "sleep_time": "22:00", "wake_time": "07:00"},
    "sync": {
        "share_url": "",
        "password": "",
        "output_dir": "/home/frame/Pictures/slideshow",
        "cache_dir": "/home/frame/.cache/framesync",
        "interval_minutes": 60,
    },
    "system": {"timezone": "America/Los_Angeles"},
    "update": {"repo": "njurgens/digital-frame"},
}

_CLAMP = {
    ("slideshow", "interval"): (1.0, 3600.0),
    ("display", "brightness"): (0, 100),
    ("sync", "interval_minutes"): (1, 1440),
}


class _SlideshowCfg:
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
    def __init__(self, data: dict):
        self._d = data

    @property
    def share_url(self) -> str:
        return str(self._d.get("share_url", ""))

    @property
    def password(self) -> str:
        return str(self._d.get("password", ""))

    @property
    def output_dir(self) -> str:
        return str(self._d.get("output_dir", "/home/frame/Pictures/slideshow"))

    @property
    def cache_dir(self) -> str:
        return str(self._d.get("cache_dir", "/home/frame/.cache/framesync"))

    @property
    def interval_minutes(self) -> int:
        return int(self._d.get("interval_minutes", 60))


class _SystemCfg:
    def __init__(self, data: dict):
        self._d = data

    @property
    def timezone(self) -> str:
        return str(self._d.get("timezone", "America/Los_Angeles"))


class _UpdateCfg:
    def __init__(self, data: dict):
        self._d = data

    @property
    def repo(self) -> str:
        return str(self._d.get("repo", "njurgens/digital-frame"))


class ConfigStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._data = deepcopy(_DEFAULTS)
        self._dirty_at: float | None = None
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with self._path.open("rb") as f:
                loaded = tomllib.load(f)
            self._merge(loaded)
        except Exception as e:
            logging.warning("config load failed (%s), backing up and using defaults", e)
            backup = self._path.with_suffix(".bak")
            try:
                shutil.copy2(self._path, backup)
            except OSError:
                pass
            self._data = deepcopy(_DEFAULTS)

    def _merge(self, loaded: dict) -> None:
        for section, section_data in loaded.items():
            if isinstance(section_data, dict):
                current = self._data.setdefault(section, {})
                for key, value in section_data.items():
                    current[key] = self._clamp(section, key, value)
            else:
                self._data[section] = section_data

    def _clamp(self, section: str, key: str, value):
        bounds = _CLAMP.get((section, key))
        if bounds is None or not isinstance(value, (int, float)):
            return value
        lo, hi = bounds
        return type(value)(max(lo, min(hi, value)))

    def tick(self, now: float) -> None:
        if self._dirty_at is not None and now - self._dirty_at >= 0.5:
            self.flush_now()

    def flush_now(self) -> None:
        disk: dict = {}
        if self._path.exists():
            try:
                with self._path.open("rb") as f:
                    disk = tomllib.load(f)
            except Exception:
                pass
        for section, key in _PROTECTED:
            disk_val = disk.get(section, {}).get(key)
            if disk_val is not None:
                self._data.setdefault(section, {})[key] = disk_val
        self._write_toml(self._data)
        self._dirty_at = None

    def set(self, section: str, key: str, value) -> None:
        value = self._clamp(section, key, value)
        self._data.setdefault(section, {})[key] = value
        if self._dirty_at is None:
            self._dirty_at = time.monotonic()

    def _write_toml(self, data: dict) -> None:
        lines = []
        for section, values in data.items():
            lines.append(f"[{section}]")
            for k, v in values.items():
                if isinstance(v, bool):
                    lines.append(f"{k} = {str(v).lower()}")
                elif isinstance(v, float):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, int):
                    lines.append(f"{k} = {v}")
                elif isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
            lines.append("")
        self._path.write_text("\n".join(lines))

    def _read_raw(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            with self._path.open("rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    @property
    def slideshow(self) -> _SlideshowCfg:
        return _SlideshowCfg(self._data.setdefault("slideshow", {}))

    @property
    def display(self) -> _DisplayCfg:
        return _DisplayCfg(self._data.setdefault("display", {}))

    @property
    def sleep(self) -> _SleepCfg:
        return _SleepCfg(self._data.setdefault("sleep", {}))

    @property
    def sync(self) -> _SyncCfg:
        return _SyncCfg(self._data.setdefault("sync", {}))

    @property
    def system(self) -> _SystemCfg:
        return _SystemCfg(self._data.setdefault("system", {}))

    @property
    def update(self) -> _UpdateCfg:
        return _UpdateCfg(self._data.setdefault("update", {}))
