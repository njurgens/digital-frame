from __future__ import annotations

from datetime import datetime
import threading
from zoneinfo import ZoneInfo

from pygame import Surface

from piframe.assets import Assets, FONT_SIZE_BODY, FONT_SIZE_CLOCK
from piframe.types import COLOUR_CLOCK_TEXT, SCREEN_H


class ClockWidget:
    _TZ_DEFAULT = "America/Los_Angeles"

    def __init__(self, assets: Assets):
        self._assets = assets
        self._tz = ZoneInfo(self._TZ_DEFAULT)
        self._surfaces: tuple[Surface, Surface] | None = None
        self._last_minute: int = -1
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._thread.start()

    def _tick_loop(self):
        while not self._stop.is_set():
            now = datetime.now(self._tz)
            if now.minute != self._last_minute:
                self._render_surfaces(now)
                self._last_minute = now.minute
            self._stop.wait(timeout=30)

    def _render_surfaces(self, now: datetime):
        time_str = now.strftime("%-I:%M")
        date_str = now.strftime("%A, %B %-d")
        time_font = self._assets.font_bold(FONT_SIZE_CLOCK)
        date_font = self._assets.font(FONT_SIZE_BODY)
        time_surf, _ = time_font.render(time_str, COLOUR_CLOCK_TEXT)
        date_surf, _ = date_font.render(date_str, COLOUR_CLOCK_TEXT)
        with self._lock:
            self._surfaces = (time_surf, date_surf)

    def set_timezone(self, tz_name: str):
        self._tz = ZoneInfo(tz_name)
        self._last_minute = -1

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)

    def draw(self, screen: Surface):
        with self._lock:
            surfs = self._surfaces
        if surfs is None:
            return
        time_surf, date_surf = surfs
        x = 24
        date_y = SCREEN_H - 20 - date_surf.get_height()
        time_y = date_y - 4 - time_surf.get_height()
        screen.blit(time_surf, (x, time_y))
        screen.blit(date_surf, (x, date_y))
