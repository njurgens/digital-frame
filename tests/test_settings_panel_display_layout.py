from __future__ import annotations

from pathlib import Path

import pygame

from piframe.config_store import ConfigStore
from piframe.settings_panel import Section, SettingsPanel
from piframe.widgets.horizontal_slider import HorizontalSlider


class _StubFont:
    def render(self, _text: str, _colour: tuple[int, int, int]) -> tuple[pygame.Surface, pygame.Rect]:
        surf = pygame.Surface((24, 12), pygame.SRCALPHA)
        return surf, surf.get_rect()


class _StubAssets:
    def icon(self, _size: int) -> _StubFont:
        return _StubFont()

    def font(self, _size: int) -> _StubFont:
        return _StubFont()

    def font_bold(self, _size: int) -> _StubFont:
        return _StubFont()


def _make_panel(tmp_path: Path) -> SettingsPanel:
    return SettingsPanel(assets=_StubAssets(), config=ConfigStore(tmp_path / "config.toml"))


def test_display_brightness_uses_horizontal_slider(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)

    assert isinstance(panel._brightness_slider, HorizontalSlider)
    assert panel._brightness_slider.rect.width > panel._brightness_slider.rect.height


def test_display_brightness_drag_updates_config_value(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel._active_section = Section.DISPLAY

    start = panel._brightness_slider.rect.center
    end = (panel._brightness_slider.rect.right - 1, panel._brightness_slider.rect.centery)

    panel.on_tap(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=start, button=1))
    panel.on_tap(pygame.event.Event(pygame.MOUSEMOTION, pos=end, rel=(100, 0), buttons=(1, 0, 0)))
    panel.on_tap(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=end, button=1))

    assert panel._brightness_slider.value == 100
    assert panel._config.display.brightness == 100


def test_display_brightness_syncs_from_config(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel._config.set("display", "brightness", 33)

    panel.sync_from_config()

    assert panel._brightness_slider.value == 33


def test_open_resyncs_brightness_from_config(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel._brightness_slider.set_value(72)
    panel._config.set("display", "brightness", 21)

    panel.open()

    assert panel._visible is True
    assert panel._brightness_slider.value == 21
