from __future__ import annotations

import datetime
import threading
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pygame
from pygame import Surface

from piframe.assets import Assets, FONT_SIZE_BODY, FONT_SIZE_CLOCK
from piframe.types import COLOUR_CLOCK_TEXT, COLOUR_TEXT_SECONDARY


class ClockWidget:
    _TEXT_X = 14
    _TEXT_Y = 14
    _DATE_GAP = 4
    _BUBBLE_PADDING = 8
    _BUBBLE_RADIUS = 12
    _BUBBLE_COLOUR = (0, 0, 0, 120)

    def __init__(self, assets: Assets):
        self._assets = assets
        self._timezone = self._default_timezone()
        self._surfaces: tuple[Surface, Surface] | None = None
        self._visible = True
        self._dirty = False
        self._pending_now: datetime.datetime | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._render_surfaces(datetime.datetime.now(self._timezone))
        self._thread = threading.Thread(target=self._ticker, daemon=True)
        self._thread.start()

    def _default_timezone(self) -> datetime.tzinfo:
        zoneinfo_root = Path("/usr/share/zoneinfo")
        localtime_path = Path("/etc/localtime")
        try:
            resolved = localtime_path.resolve(strict=True)
            zone_name = str(resolved.relative_to(zoneinfo_root))
            return ZoneInfo(zone_name)
        except (OSError, ValueError, ZoneInfoNotFoundError):
            pass
        try:
            zone_name = Path("/etc/timezone").read_text(encoding="utf-8").strip()
            if zone_name:
                return ZoneInfo(zone_name)
        except (OSError, ValueError, ZoneInfoNotFoundError):
            pass
        return ZoneInfo("UTC")

    def _ticker(self):
        while not self._stop_event.is_set():
            with self._lock:
                tz = self._timezone
            now = datetime.datetime.now(tz)
            with self._lock:
                self._pending_now = now
                self._dirty = True
            seconds_until = 60 - now.second
            self._stop_event.wait(seconds_until)

    def _render_surfaces(self, now: datetime.datetime):
        time_str = now.strftime("%-H:%M")
        date_str = now.strftime("%A, %B %-d")
        time_font = self._assets.font_bold(FONT_SIZE_CLOCK)
        date_font = self._assets.font(FONT_SIZE_BODY)
        time_surf, _ = time_font.render(time_str, COLOUR_CLOCK_TEXT)
        date_surf, _ = date_font.render(date_str, COLOUR_TEXT_SECONDARY)
        with self._lock:
            self._surfaces = (time_surf, date_surf)

    def update_timezone(self, tz_name: str | datetime.tzinfo):
        tz = ZoneInfo(tz_name) if isinstance(tz_name, str) else tz_name
        with self._lock:
            self._timezone = tz
        self._render_surfaces(datetime.datetime.now(self._timezone))
        with self._lock:
            self._dirty = True

    def set_timezone(self, tz_name: str | datetime.tzinfo):
        self.update_timezone(tz_name)

    def set_visible(self, visible: bool):
        with self._lock:
            self._visible = visible

    def tick(self):
        with self._lock:
            now = datetime.datetime.now(self._timezone)
            self._pending_now = now
            self._dirty = True

    def update(self, dt: float) -> None:
        _ = dt
        with self._lock:
            if not self._dirty:
                return
            now = self._pending_now or datetime.datetime.now(self._timezone)
            self._pending_now = None
            self._dirty = False
        self._render_surfaces(now)

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2)

    def draw(self, screen: Surface):
        with self._lock:
            if not self._visible:
                return
            surfs = self._surfaces
        if surfs is None:
            return
        time_surf, date_surf = surfs
        text_x = self._TEXT_X
        text_y = self._TEXT_Y
        text_h = time_surf.get_height() + self._DATE_GAP + date_surf.get_height()
        text_w = max(time_surf.get_width(), date_surf.get_width())
        bubble = pygame.Surface(
            (
                text_w + self._BUBBLE_PADDING * 2,
                text_h + self._BUBBLE_PADDING * 2,
            ),
            pygame.SRCALPHA,
        )
        pygame.draw.rect(
            bubble,
            self._BUBBLE_COLOUR,
            bubble.get_rect(),
            border_radius=self._BUBBLE_RADIUS,
        )
        screen.blit(
            bubble,
            (text_x - self._BUBBLE_PADDING, text_y - self._BUBBLE_PADDING),
        )
        screen.blit(time_surf, (text_x, text_y))
        screen.blit(date_surf, (text_x, text_y + time_surf.get_height() + self._DATE_GAP))
