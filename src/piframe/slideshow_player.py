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
    """
    Full-screen slideshow player with timed transitions.

    Manages a playlist of photo paths, advancing on an interval and rendering
    crossfade/slide/cut transitions between images.  The image directory is
    rescanned each cycle so newly synced photos appear without a restart.
    """

    def __init__(
        self,
        config: ConfigStore,
        cache: PhotoCache,
        screen_size: tuple[int, int],
        assets: Assets | None = None,
    ):
        """
        Initialise the player and load the initial playlist.

        Args:
            config: Application configuration (interval, fit mode, shuffle, etc.).
            cache: Photo cache for pre-rendered surfaces.
            screen_size: ``(width, height)`` of the display.
            assets: Asset provider for icons (used by the pause PiP indicator).

        """
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
        """
        Re-read the output directory and rebuild the playlist.

        Loads all supported image files, optionally shuffles them, and
        pre-loads the first slide into the cache.
        """
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
        """
        Tick the player by *dt* seconds.

        Advances to the next slide when the interval elapses and drives
        in-progress transitions toward completion.

        Args:
            dt: Elapsed time in seconds since the last tick.

        """
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
        """
        Move to the next (or previous) slide and start a transition.

        Args:
            direction: ``1`` for forward, ``-1`` for backward.

        """
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
        """Advance to the previous slide."""
        self.advance(direction=-1)

    def skip(self) -> None:
        """Advance to the next slide."""
        self.advance(direction=1)

    def skip_next(self) -> None:
        """Alias of :meth:`skip` for API compatibility."""
        return self.skip()

    def draw(self, screen: Surface) -> None:
        """
        Render the current slide (and transition) onto *screen*.

        Args:
            screen: Target pygame surface.

        """
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
        """
        Draw a small pause indicator pill when the player is paused.

        Args:
            screen: Target pygame surface.

        """
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
        """Whether the slideshow timer is currently paused."""
        return self._paused

    @is_paused.setter
    def is_paused(self, value: bool):
        """Set the paused state."""
        self._paused = value
