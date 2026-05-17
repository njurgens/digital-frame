from pathlib import Path
from unittest.mock import Mock

import pygame

from piframe.assets import IC_PAUSE, IC_PLAY
from piframe.config_store import ConfigStore
from piframe.overlay_ui import DISMISS_BAR, GEAR_RECT, NEXT_RECT, PLAY_RECT, PREV_RECT, OverlayUI
from piframe.types import COLOUR_OVERLAY_BTN_BG


class _StubFont:
    def render(self, _text: str, _colour: tuple[int, int, int]) -> tuple[pygame.Surface, pygame.Rect]:
        surf = pygame.Surface((8, 8), pygame.SRCALPHA)
        surf.fill((*_colour, 255))
        return surf, surf.get_rect()


class _StubAssets:
    def icon(self, _size: int) -> _StubFont:
        return _StubFont()

    def font(self, _size: int) -> _StubFont:
        return _StubFont()


def _make_overlay(tmp_path: Path) -> OverlayUI:
    return OverlayUI(_StubAssets(), ConfigStore(tmp_path / "config.toml"))


def test_overlay_button_background_preserves_alpha(tmp_path: Path) -> None:
    overlay = _make_overlay(tmp_path)
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)
    rect = pygame.Rect(200, 200, 48, 48)

    overlay._draw_overlay_button(screen, rect)

    inside = screen.get_at(rect.center)
    outside = screen.get_at((rect.left - 1, rect.top - 1))

    assert inside[:3] == COLOUR_OVERLAY_BTN_BG[:3]
    assert inside[3] == COLOUR_OVERLAY_BTN_BG[3]
    assert outside[3] == 0


def test_show_and_hide_manage_visibility_and_flags(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 100.0)
    overlay.show()
    assert overlay._visible is True
    assert overlay.dismissed is False
    assert overlay._dismiss_at == 105.0
    overlay.hide()
    assert overlay._visible is False
    assert overlay.dismissed is True
    assert overlay._dragging_slider is False


def test_show_while_paused_has_no_dismiss_timer(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    overlay._paused = True
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 100.0)
    overlay.show()
    assert overlay._dismiss_at is None


def test_update_hides_after_timer_expiry(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    overlay._visible = True
    overlay._dismiss_at = 10.0
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 10.0)
    overlay.update(0.016)
    assert overlay._visible is False
    assert overlay.dismissed is True


def test_draw_noop_when_hidden(tmp_path: Path) -> None:
    overlay = _make_overlay(tmp_path)
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)
    overlay.draw(screen)
    assert screen.get_at((640, 400))[3] == 0


def test_draw_visible_renders_scrim_and_progress_bar(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 100.0)
    overlay.show()
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 102.5)
    overlay.draw(screen)
    assert screen.get_at((640, 400))[3] > 0
    assert screen.get_at((10, 1))[3] == 255


def test_draw_hides_progress_bar_when_paused(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 10.0)
    overlay.show()
    overlay.set_paused(True)
    overlay.draw(screen)
    assert screen.get_at((10, 1))[3] < 255


def test_draw_uses_play_icon_when_paused_and_pause_when_playing(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 1.0)
    overlay.show()
    captured: list[str] = []
    original = overlay._draw_icon_centered

    def _capture(_screen, icon, size, center):
        if center == PLAY_RECT.center:
            captured.append(icon)
        return original(_screen, icon, size, center)

    overlay._draw_icon_centered = _capture
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)
    overlay.set_paused(True)
    overlay.draw(screen)
    overlay.set_paused(False)
    overlay.draw(screen)
    assert captured[0] == IC_PLAY
    assert captured[1] == IC_PAUSE


def test_draw_renders_visible_playback_icons(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 10.0)
    overlay.show()
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)
    overlay.draw(screen)
    for center in (PREV_RECT.center, PLAY_RECT.center, NEXT_RECT.center):
        px = screen.get_at(center)
        assert px[:3] == (255, 255, 255)
        assert px[3] == 255


def test_on_tap_routes_actions(tmp_path: Path) -> None:
    overlay = _make_overlay(tmp_path)
    overlay.show()
    assert overlay.on_tap(DISMISS_BAR.center) == "dismiss"
    assert overlay.on_tap(GEAR_RECT.center) == "settings"
    assert overlay.on_tap(PREV_RECT.center) == "prev"
    assert overlay.on_tap(PLAY_RECT.center) == "play_pause"
    assert overlay.on_tap(NEXT_RECT.center) == "next"
    assert overlay.on_tap((5, 5)) is None


def test_on_drag_updates_brightness_and_uses_slider_callback(tmp_path: Path) -> None:
    overlay = _make_overlay(tmp_path)
    overlay.show()
    slider_cb = Mock()
    overlay._slider.on_change = slider_cb
    y = overlay._slider.rect.top + 20
    overlay.on_drag((overlay._slider.rect.centerx, y))
    assert overlay._dragging_slider is True
    assert overlay._slider.value == overlay._brightness
    assert overlay._slider.dirty is True
    slider_cb.assert_called_once_with(overlay._slider.value)


def test_on_drag_uses_overlay_callback_when_slider_callback_missing(tmp_path: Path) -> None:
    overlay = _make_overlay(tmp_path)
    overlay.show()
    overlay._slider.on_change = None
    cb = Mock()
    overlay.on_brightness_change = cb
    y = overlay._slider.rect.top + 30
    overlay.on_drag((overlay._slider.rect.centerx, y))
    cb.assert_called_once_with(overlay._slider.value)


def test_drag_helpers_and_setters(tmp_path: Path, monkeypatch) -> None:
    overlay = _make_overlay(tmp_path)
    overlay._dragging_slider = True
    overlay.stop_drag()
    assert overlay.is_dragging_slider() is False

    monkeypatch.setattr("piframe.overlay_ui.time.monotonic", lambda: 50.0)
    overlay.set_paused(True)
    assert overlay._dismiss_at is None
    overlay.set_paused(False)
    assert overlay._dismiss_at == 55.0

    overlay.set_brightness(200)
    assert overlay._brightness == 100
    assert overlay._slider.value == 100
    assert overlay._slider.dirty is True
