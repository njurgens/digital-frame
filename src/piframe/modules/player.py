"""Player module: constructs a SlideshowPlayer with its dependencies."""
from __future__ import annotations

from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.slideshow_player import SlideshowPlayer
from piframe.types import SCREEN_H, SCREEN_W


class PlayerModule(DimModule[SlideshowPlayer]):
    """Construct a ``SlideshowPlayer`` wired to a cache and assets."""

    def create(
        self,
        config: ConfigStore,
        *,
        cache: PhotoCache,
        assets: Assets,
        **deps: object,
    ) -> SlideshowPlayer:
        """
        Build a slideshow player with the given dependencies.

        Args:
            config: Application configuration.
            cache: Photo cache for pre-rendered surfaces.
            assets: Asset provider for icons.
            **deps: Unused.

        Returns
        -------
            A ``SlideshowPlayer`` instance.

        """
        return SlideshowPlayer(
            config=config,
            cache=cache,
            screen_size=(SCREEN_W, SCREEN_H),
            assets=assets,
        )
