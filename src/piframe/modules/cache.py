"""Cache module: constructs a PhotoCache for composited surfaces."""

from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.types import SCREEN_H, SCREEN_W


class CacheModule(DimModule[PhotoCache]):
    """Construct a ``PhotoCache`` with the default surface cache directory.

    The surface cache is a player implementation detail, not provider
    storage, so its location is not config-driven.
    """

    def create(self, config: ConfigStore, **deps: object) -> PhotoCache:
        """Build a photo cache at the default surface cache location.

        Args:
            config: Application configuration (unused; retained for the
                module protocol).
            **deps: Unused.

        Returns:
            A ``PhotoCache`` instance.

        """
        return PhotoCache(screen_size=(SCREEN_W, SCREEN_H))
