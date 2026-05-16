from __future__ import annotations

import datetime
import threading
from zoneinfo import ZoneInfo

from pygame import Surface

from piframe.assets import Assets, FONT_SIZE_BODY, FONT_SIZE_CLOCK
from piframe.types import COLOUR_CLOCK_TEXT, COLOUR_TEXT_SECONDARY


class ClockWidget:
    _TZ_DEFAULT = "America/Los_Angeles"

    def __init__(self, assets: Assets):
        self._assets = assets
        self._timezone = ZoneInfo(self._TZ_DEFAULT)
        self._surfaces: tuple[Surface, Surface] | None = None
        self._dirty = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._ticker, daemon=True)
        self._thread.start()

    def _ticker(self):
        while not self._stop_event.is_set():
            now = datetime.datetime.now(self._timezone)
            self._render_surfaces(now)
            with self._lock:
                self._dirty = True
            seconds_until = 60 - now.second
            self._stop_event.wait(timeout=seconds_until)

    def _render_surfaces(self, now: datetime.datetime):
        time_str = now.strftime("%-I:%M %p")
        date_str = now.strftime("%A, %B %-d")
        time_font = self._assets.font_bold(FONT_SIZE_CLOCK)
        date_font = self._assets.font(FONT_SIZE_BODY)
        time_surf, _ = time_font.render(time_str, COLOUR_CLOCK_TEXT)
        date_surf, _ = date_font.render(date_str, COLOUR_TEXT_SECONDARY)
        with self._lock:
            self._surfaces = (time_surf, date_surf)

    def update_timezone(self, tz_name: str):
        self._timezone = ZoneInfo(tz_name)
        self._render_surfaces(datetime.datetime.now(self._timezone))
        with self._lock:
            self._dirty = True

    def update(self, dt: float) -> None:
        _ = dt

    def stop(self):
        self._stop_event.set()
        self._thread.join(timeout=2)

    def draw(self, screen: Surface):
        with self._lock:
            surfs = self._surfaces
        if surfs is None:
            return
        time_surf, date_surf = surfs
        screen.blit(time_surf, (14, 14))
        screen.blit(date_surf, (14, 14 + time_surf.get_height() + 4))
