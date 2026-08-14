"""Cache module: constructs a PhotoCache from config."""

from __future__ import annotations

from pathlib import Path

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.types import SCREEN_H, SCREEN_W


class CacheModule(DimModule[PhotoCache]):
    """Construct a ``PhotoCache`` with screen size and cache dir from config."""

    def create(self, config: ConfigStore, **deps: object) -> PhotoCache:
        """Build a photo cache pointing at the configured cache directory.

        Args:
            config: Application configuration.
            **deps: Unused.

        Returns:
        -------
            A ``PhotoCache`` instance.

        """
        return PhotoCache(
            screen_size=(SCREEN_W, SCREEN_H),
            cache_dir=Path(config.sync.cache_dir),
        )
