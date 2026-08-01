from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.assets import IC_LOCK, IC_WIFI, IC_WIFI_OFF
from piframe.types import (
    COLOUR_CONNECTED,
    COLOUR_NAV_ACTIVE_BG,
    COLOUR_TEXT_PRIMARY,
    COLOUR_TEXT_SECONDARY,
)
from piframe.widgets.base import Widget

ROW_H = 56


class WifiListItem(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        network: object,
        current_ssid: str = "",
        assets=None,
        on_tap: Callable[[object], None] | None = None,
        on_long_press: Callable[[object], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self.network = network
        self.current_ssid = current_ssid
        self._assets = assets
        self.on_tap = on_tap
        self.on_long_press = on_long_press
        self._press_start: float | None = None

    def draw(self, screen: pygame.Surface) -> None:
        net = self.network
        rect = self.rect
        is_connected = net.ssid == self.current_ssid

        if is_connected:
            pygame.draw.rect(screen, COLOUR_NAV_ACTIVE_BG[:3], rect)

        if self._assets:
            icon_font = self._assets.icon(24)
            body_font = self._assets.font(18)
            caption_font = self._assets.font(14)

            signal_char = IC_WIFI if net.signal_level >= 1 else IC_WIFI_OFF
            icon_surf, _ = icon_font.render(signal_char, COLOUR_TEXT_PRIMARY[:3])
            screen.blit(icon_surf, (rect.x + 8, rect.centery - icon_surf.get_height() // 2))

            x_ssid = rect.x + 40
            if net.security and net.security not in ("--", ""):
                lock_surf, _ = self._assets.icon(24).render(IC_LOCK, COLOUR_TEXT_SECONDARY[:3])
                screen.blit(lock_surf, (rect.x + 36, rect.centery - lock_surf.get_height() // 2))
                x_ssid = rect.x + 60

            ssid_surf, _ = body_font.render(net.ssid, COLOUR_TEXT_PRIMARY[:3])
            screen.blit(ssid_surf, (x_ssid, rect.centery - ssid_surf.get_height() // 2 - 6))

            sec_label = net.security if net.security and net.security != "--" else "Open"
            sec_surf, _ = caption_font.render(sec_label, COLOUR_TEXT_SECONDARY[:3])
            screen.blit(sec_surf, (x_ssid, rect.centery + 4))

            if is_connected:
                pygame.draw.circle(screen, COLOUR_CONNECTED[:3], (rect.right - 16, rect.centery), 4)

    def handle_event(self, event: pygame.event.Event) -> bool:
        import time

        if event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos):
            self._press_start = time.monotonic()
            return True
        if event.type == pygame.MOUSEBUTTONUP and self.rect.collidepoint(event.pos):
            if self._press_start is not None:
                duration = time.monotonic() - self._press_start
                self._press_start = None
                if duration >= 0.6:
                    if self.on_long_press:
                        self.on_long_press(self.network)
                else:
                    if self.on_tap:
                        self.on_tap(self.network)
                return True
        return False
