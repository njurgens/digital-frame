"""Slideshow player: rescan, advance, transition, draw."""

from __future__ import annotations

import time
from pathlib import Path

import pygame
from pygame import Rect, Surface

from piframe.assets import IC_PAUSE, Assets
from piframe.config_store import ConfigStore
from piframe.photo_cache import PhotoCache
from piframe.types import TRANS_DURATION


class SlideshowPlayer:
    def __init__(
        self,
        config: ConfigStore,
        cache: PhotoCache,
        screen_size: tuple[int, int],
        assets: Assets | None = None,
    ):
        self._config = config
        self._cache = cache
        self._assets = assets
        self._w, self._h = screen_size
        self._playlist: list[Path] = []
        self._index: int = 0
        self._current_surf: Surface | None = None
        self._next_surf: Surface | None = None
        self._elapsed: float = 0.0
        self._trans_t: float = 0.0
        self._in_transition: bool = False
        self._trans_start: float = 0.0
        self._direction: int = 1
        self._paused: bool = False

        self._slide_rect: Rect = Rect(0, 0, self._w, self._h)
        self.rescan()

    def rescan(self) -> None:
        output_dir = Path(self._config.sync.output_dir)
        exts = {".jpg", ".jpeg", ".png", ".gif"}
        files = (
            sorted([p for p in output_dir.iterdir() if p.suffix.lower() in exts])
            if output_dir.exists()
            else []
        )
        self._playlist = files
        if self._config.slideshow.shuffle:
            self._playlist = self._fisher_yates(self._playlist)
        self._index = 0
        if self._playlist:
            self._current_surf = self._cache.get(
                self._playlist[0],
                self._config.slideshow.fit_mode,
                self._w,
                self._h,
            )
        else:
            self._current_surf = None

    def _fisher_yates(self, items: list) -> list:
        import random

        lst = list(items)
        for i in range(len(lst) - 1, 0, -1):
            j = random.randint(0, i)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

    def update(self, dt: float) -> None:
        if self._paused or not self._playlist:
            return
        interval = self._config.slideshow.interval
        trans_dur = TRANS_DURATION

        if self._in_transition:
            elapsed = time.monotonic() - self._trans_start
            self._trans_t = min(1.0, elapsed / trans_dur)
            if self._trans_t >= 1.0:
                self._commit_transition()
        else:
            self._elapsed += dt
            if self._elapsed >= interval:
                self.advance()

    def advance(self, direction: int = 1) -> None:
        if not self._playlist:
            return
        self._direction = direction
        next_idx = (self._index + direction) % len(self._playlist)
        self._next_surf = self._cache.get(
            self._playlist[next_idx],
            self._config.slideshow.fit_mode,
            self._w,
            self._h,
        )
        self._index = next_idx
        self._start_transition()

    def _start_transition(self) -> None:
        self._trans_start = time.monotonic()
        self._in_transition = True
        self._trans_t = 0.0

    def _commit_transition(self) -> None:
        self._trans_t = 1.0
        self._current_surf = self._next_surf
        self._next_surf = None
        self._in_transition = False
        self._elapsed = 0.0

    def go_back(self) -> None:
        self.advance(direction=-1)

    def skip(self) -> None:
        self.advance(direction=1)

    def skip_next(self) -> None:
        return self.skip()

    def draw(self, screen: Surface) -> None:
        if self._current_surf is None:
            screen.fill((0, 0, 0))
            return
        if self._in_transition and self._next_surf is not None:
            trans = self._config.slideshow.transition
            if trans == "crossfade":
                screen.blit(self._current_surf, (0, 0))
                alpha_surf = self._next_surf.copy()
                alpha_surf.set_alpha(int(self._trans_t * 255))
                screen.blit(alpha_surf, (0, 0))
            elif trans == "slide":
                cur_x = int(-self._direction * self._trans_t * self._w)
                next_x = int(self._direction * (1.0 - self._trans_t) * self._w)
                screen.blit(self._current_surf, (cur_x, 0))
                screen.blit(self._next_surf, (next_x, 0))
            else:
                screen.blit(
                    self._next_surf if self._trans_t >= 0.5 else self._current_surf, (0, 0)
                )
        else:
            screen.blit(self._current_surf, (0, 0))

    def draw_pip(self, screen: Surface) -> None:
        if not self._paused:
            return
        pill_rect = pygame.Rect(12, 762, 26, 26)
        pygame.draw.rect(screen, (0, 0, 0), pill_rect, border_radius=13)
        if self._assets is not None:
            icon_font = self._assets.icon(24)
            icon_surf, _ = icon_font.render(IC_PAUSE, (255, 255, 255))
            screen.blit(
                icon_surf,
                (
                    pill_rect.centerx - icon_surf.get_width() // 2,
                    pill_rect.centery - icon_surf.get_height() // 2,
                ),
            )

    @property
    def is_paused(self) -> bool:
        return self._paused

    @is_paused.setter
    def is_paused(self, value: bool):
        self._paused = value
