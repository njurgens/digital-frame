from __future__ import annotations

from pathlib import Path

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.types import SCREEN_H, SCREEN_W


class CacheModule(DimModule[PhotoCache]):
    def create(self, config: ConfigStore, **deps: object) -> PhotoCache:
        return PhotoCache(
            screen_size=(SCREEN_W, SCREEN_H),
            cache_dir=Path(config.sync.cache_dir),
        )
