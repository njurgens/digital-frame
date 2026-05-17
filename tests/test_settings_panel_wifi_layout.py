from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame

from piframe.config_store import ConfigStore
from piframe.settings_panel import SettingsPanel, Section, WIFI_LIST_Y
from piframe.types import WifiNetwork


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


def test_wifi_list_shrinks_to_avoid_password_input_overlap(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel._wifi_networks = [
        WifiNetwork("Net 1", "WPA2", 80),
        WifiNetwork("Net 2", "WPA2", 70),
        WifiNetwork("Net 3", "WPA2", 60),
    ]

    panel._wifi_password_ssid = None
    panel._rebuild_wifi_items()
    assert len(panel._wifi_items) == 3

    panel._wifi_password_ssid = "Net 1"
    panel._rebuild_wifi_items()
    assert len(panel._wifi_items) == 1
    assert panel._wifi_items[0].rect.bottom <= panel._wifi_password_input.rect.top


def test_wifi_secure_tap_rebuilds_list_for_password_prompt(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel.on_wifi_result(
        SimpleNamespace(
            operation="scan",
            success=True,
            data=[
                WifiNetwork("Secure", "WPA2", 80),
                WifiNetwork("Other", "WPA2", 70),
                WifiNetwork("Third", "WPA2", 60),
            ],
        )
    )
    assert len(panel._wifi_items) == 3

    panel._on_wifi_network_tap(WifiNetwork("Secure", "WPA2", 80))

    assert panel._wifi_password_ssid == "Secure"
    assert len(panel._wifi_items) == 1


def test_wifi_password_input_focus_triggers_keyboard_attach_callback(tmp_path: Path) -> None:
    focused = []
    panel = SettingsPanel(
        assets=_StubAssets(),
        config=ConfigStore(tmp_path / "config.toml"),
        on_focus_text=lambda w: focused.append(w),
    )
    panel._active_section = Section.WIFI
    panel._wifi_password_ssid = "Secure"
    tap_pos = panel._wifi_password_input.rect.center

    consumed = panel.on_tap(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=tap_pos, button=1))

    assert consumed is True
    assert focused == [panel._wifi_password_input]


def test_wifi_connect_result_clears_prompt_and_restores_visible_rows(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel._wifi_networks = [
        WifiNetwork("Secure", "WPA2", 80),
        WifiNetwork("Other", "WPA2", 70),
        WifiNetwork("Third", "WPA2", 60),
    ]
    panel._wifi_password_ssid = "Secure"
    panel._rebuild_wifi_items()
    assert len(panel._wifi_items) == 1

    panel.on_wifi_result(SimpleNamespace(operation="connect", success=False, data=None))

    assert panel._wifi_password_ssid is None
    assert len(panel._wifi_items) == 3


def test_wifi_list_allows_zero_visible_rows_when_no_space_above_password_input(tmp_path: Path) -> None:
    panel = _make_panel(tmp_path)
    panel._wifi_networks = [WifiNetwork("Secure", "WPA2", 80)]
    panel._wifi_password_ssid = "Secure"
    panel._wifi_password_input.rect = pygame.Rect(
        panel._wifi_password_input.rect.x,
        WIFI_LIST_Y,
        panel._wifi_password_input.rect.width,
        panel._wifi_password_input.rect.height,
    )

    panel._rebuild_wifi_items()

    assert panel._wifi_items == []
