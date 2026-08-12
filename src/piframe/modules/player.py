from __future__ import annotations

from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.slideshow_player import SlideshowPlayer
from piframe.types import SCREEN_H, SCREEN_W


class PlayerModule(DimModule[SlideshowPlayer]):
    def create(
        self,
        config: ConfigStore,
        *,
        cache: PhotoCache,
        assets: Assets,
        **deps: object,
    ) -> SlideshowPlayer:
        return SlideshowPlayer(
            config=config,
            cache=cache,
            screen_size=(SCREEN_W, SCREEN_H),
            assets=assets,
        )
