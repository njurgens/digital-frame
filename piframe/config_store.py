from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tomllib

_DEFAULTS = {
    "slideshow": {
        "interval": 30.0,
        "fit_mode": "fit",
        "shuffle": True,
        "transition": "crossfade",
    },
    "display": {
        "brightness": 80,
        "show_clock": True,
    },
    "sync": {
        "output_dir": "/home/frame/Pictures/slideshow",
    },
    "system": {
        "timezone": "America/Los_Angeles",
    },
}


class _SlideshowCfg:
    def __init__(self, data: dict):
        self._data = data

    @property
    def interval(self) -> float:
        return float(self._data.get("interval", 30.0))

    @property
    def fit_mode(self) -> str:
        mode = str(self._data.get("fit_mode", "fit"))
        return mode if mode in {"fit", "fill"} else "fit"

    @property
    def shuffle(self) -> bool:
        return bool(self._data.get("shuffle", True))

    @property
    def transition(self) -> str:
        return str(self._data.get("transition", "crossfade"))


class _DisplayCfg:
    def __init__(self, data: dict):
        self._data = data

    @property
    def show_clock(self) -> bool:
        return bool(self._data.get("show_clock", True))

    @property
    def brightness(self) -> int:
        return int(self._data.get("brightness", 80))


class _SyncCfg:
    def __init__(self, data: dict):
        self._data = data

    @property
    def output_dir(self) -> str:
        return str(self._data.get("output_dir", "/home/frame/Pictures/slideshow"))


class _SystemCfg:
    def __init__(self, data: dict):
        self._data = data

    @property
    def timezone(self) -> str:
        return str(self._data.get("timezone", "America/Los_Angeles"))


class ConfigStore:
    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._data = deepcopy(_DEFAULTS)
        try:
            with self._path.open("rb") as f:
                loaded = tomllib.load(f)
            if isinstance(loaded, dict):
                self._merge(loaded)
        except Exception:
            self._data = deepcopy(_DEFAULTS)

    def _merge(self, loaded: dict) -> None:
        for section, section_data in loaded.items():
            if isinstance(section_data, dict):
                current = self._data.setdefault(section, {})
                for key, value in section_data.items():
                    current[key] = value
            else:
                self._data[section] = section_data

    def tick(self, now: float) -> None:
        _ = now

    def set(self, section: str, key: str, value) -> None:
        self._data.setdefault(section, {})[key] = value

    @property
    def slideshow(self) -> _SlideshowCfg:
        return _SlideshowCfg(self._data.setdefault("slideshow", {}))

    @property
    def display(self) -> _DisplayCfg:
        return _DisplayCfg(self._data.setdefault("display", {}))

    @property
    def sync(self) -> _SyncCfg:
        return _SyncCfg(self._data.setdefault("sync", {}))

    @property
    def system(self) -> _SystemCfg:
        return _SystemCfg(self._data.setdefault("system", {}))
