from __future__ import annotations

import time
from collections.abc import Callable

import pygame

from piframe.assets import (
    FONT_SIZE_SECONDARY,
    IC_BRIGHTNESS,
    IC_PAUSE,
    IC_PLAY,
    IC_SETTINGS,
    IC_SKIP_NEXT,
    IC_SKIP_PREV,
    ICON_SIZE_NORMAL,
    ICON_SIZE_OVERLAY,
    Assets,
)
from piframe.config_store import ConfigStore
from piframe.types import (
    COLOUR_OVERLAY_BTN_BD,
    COLOUR_OVERLAY_BTN_BG,
    COLOUR_OVERLAY_SCRIM,
    OVERLAY_DISMISS,
    SCREEN_H,
    SCREEN_W,
)
from piframe.widgets.vertical_slider import VerticalSlider

GEAR_CENTER = (1240, 33)
GEAR_RECT = pygame.Rect(1221, 14, 38, 38)
SUN_HI_CENTER = (1240, 108)
SUN_LO_CENTER = (1240, 744)
SLIDER_RECT = pygame.Rect(1238, 130, 4, 588)
BRIGHTNESS_LABEL_CENTER = (1240, 776)

PREV_RECT = pygame.Rect(508, 732, 48, 48)
PLAY_RECT = pygame.Rect(572, 728, 56, 56)
NEXT_RECT = pygame.Rect(644, 732, 48, 48)
DISMISS_BAR = pygame.Rect(0, 0, 1280, 3)


class OverlayUI:
    def __init__(self, assets: Assets, config: ConfigStore):
        self._assets = assets
        self._config = config
        self._visible: bool = False
        self._dismiss_at: float | None = None
        self._paused: bool = False
        self._brightness: int = max(0, min(100, int(config.display.brightness)))
        self._slider = VerticalSlider(
            pygame.Rect(1220, 130, 40, 588),
            initial_value=self._brightness,
        )
        self._dragging_slider: bool = False
        self.dismissed: bool = False
        self.on_brightness_change: Callable[[int], None] | None = None
        self._slider.on_change = self._on_slider_change

    def _on_slider_change(self, value: int) -> None:
        self._brightness = value
        if self.on_brightness_change is not None:
            self.on_brightness_change(value)

    def show(self):
        self._visible = True
        self.dismissed = False
        self._dismiss_at = time.monotonic() + OVERLAY_DISMISS if not self._paused else None

    def hide(self):
        self._visible = False
        self.dismissed = True
        self._dragging_slider = False

    def update(self, dt: float):
        _ = dt
        if self._dismiss_at is not None and time.monotonic() >= self._dismiss_at:
            self.hide()

    def _draw_overlay_button(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        button = pygame.Surface(rect.size, pygame.SRCALPHA)
        button_rect = button.get_rect()
        pygame.draw.rect(button, COLOUR_OVERLAY_BTN_BG, button_rect, border_radius=12)
        pygame.draw.rect(button, COLOUR_OVERLAY_BTN_BD, button_rect, width=1, border_radius=12)
        screen.blit(button, rect.topleft)

    def _draw_icon_centered(self, screen: pygame.Surface, icon: str, size: int, center: tuple[int, int]) -> None:
        surf, r = self._assets.icon(size).render(icon, (255, 255, 255))
        r.center = center
        screen.blit(surf, r)

    def draw(self, screen: pygame.Surface):
        if not self._visible:
            return

        scrim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        scrim.fill(COLOUR_OVERLAY_SCRIM)
        screen.blit(scrim, (0, 0))

        # Drain the dismiss bar proportionally; hide entirely when paused
        if not self._paused and self._dismiss_at is not None:
            remaining = max(0.0, self._dismiss_at - time.monotonic())
            bar_w = int(SCREEN_W * remaining / OVERLAY_DISMISS)
            if bar_w > 0:
                pygame.draw.rect(screen, COLOUR_OVERLAY_BTN_BD[:3], pygame.Rect(0, 0, bar_w, 3))

        self._draw_overlay_button(screen, GEAR_RECT)
        self._draw_icon_centered(screen, IC_SETTINGS, ICON_SIZE_NORMAL, GEAR_CENTER)

        self._draw_icon_centered(screen, IC_BRIGHTNESS, ICON_SIZE_NORMAL, SUN_HI_CENTER)
        self._draw_icon_centered(screen, IC_BRIGHTNESS, ICON_SIZE_NORMAL, SUN_LO_CENTER)

        self._slider.draw(screen)

        pct_text = f"{self._brightness}%"
        pct_surf, pct_rect = self._assets.font(FONT_SIZE_SECONDARY).render(pct_text, (255, 255, 255))
        pct_rect.center = BRIGHTNESS_LABEL_CENTER
        screen.blit(pct_surf, pct_rect)

        for rect, icon, size in [
            (PREV_RECT, IC_SKIP_PREV, ICON_SIZE_NORMAL),
            (PLAY_RECT, IC_PLAY if self._paused else IC_PAUSE, ICON_SIZE_OVERLAY),
            (NEXT_RECT, IC_SKIP_NEXT, ICON_SIZE_NORMAL),
        ]:
            self._draw_overlay_button(screen, rect)
            self._draw_icon_centered(screen, icon, size, rect.center)

    def on_tap(self, pos: tuple[int, int]) -> str | None:
        if not self._visible:
            return None
        if DISMISS_BAR.collidepoint(pos):
            return "dismiss"
        if GEAR_RECT.collidepoint(pos):
            self._extend_dismiss()
            return "settings"
        if PREV_RECT.collidepoint(pos):
            self._extend_dismiss()
            return "prev"
        if PLAY_RECT.collidepoint(pos):
            self._extend_dismiss()
            return "play_pause"
        if NEXT_RECT.collidepoint(pos):
            self._extend_dismiss()
            return "next"
        return None

    def on_drag(self, pos: tuple[int, int]):
        if not self._visible:
            return
        if self._dragging_slider or self._slider.rect.inflate(20, 0).collidepoint(pos):
            self._dragging_slider = True
            value = self._slider._y_to_value(pos[1])
            self._slider.value = value
            self._brightness = value
            self._slider.dirty = True
            if self._slider.on_change is not None:
                self._slider.on_change(value)
            elif self.on_brightness_change is not None:
                self.on_brightness_change(value)
            self._extend_dismiss()

    def stop_drag(self) -> None:
        self._dragging_slider = False

    def is_dragging_slider(self) -> bool:
        return self._dragging_slider

    def _extend_dismiss(self):
        if not self._paused:
            self._dismiss_at = time.monotonic() + OVERLAY_DISMISS

    def set_paused(self, paused: bool):
        self._paused = paused
        if paused:
            self._dismiss_at = None
        else:
            self._extend_dismiss()

    def set_brightness(self, pct: int):
        self._brightness = max(0, min(100, int(pct)))
        self._slider.value = self._brightness
        self._slider.dirty = True
