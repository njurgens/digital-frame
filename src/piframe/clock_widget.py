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
        self._pending_now: datetime.datetime | None = None
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._render_surfaces(datetime.datetime.now(self._timezone))
        self._thread = threading.Thread(target=self._ticker, daemon=True)
        self._thread.start()

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

    def update_timezone(self, tz_name: str):
        with self._lock:
            self._timezone = ZoneInfo(tz_name)
        self._render_surfaces(datetime.datetime.now(self._timezone))
        with self._lock:
            self._dirty = True

    def set_timezone(self, tz_name: str):
        self.update_timezone(tz_name)

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
            surfs = self._surfaces
        if surfs is None:
            return
        time_surf, date_surf = surfs
        screen.blit(time_surf, (14, 14))
        screen.blit(date_surf, (14, 14 + time_surf.get_height() + 4))
