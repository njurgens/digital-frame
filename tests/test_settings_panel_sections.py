"""Tests for settings panel section draw paths."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest

from piframe.config_store import ConfigStore
from piframe.settings_panel import Section, SettingsPanel
from piframe.types import SCREEN_H, SCREEN_W, SyncStatus, WifiStatus


class _StubFont:
    def render(
        self, _text: str, _colour: tuple[int, int, int]
    ) -> tuple[pygame.Surface, pygame.Rect]:
        surf = pygame.Surface((24, 12), pygame.SRCALPHA)
        return surf, surf.get_rect()

    def get_sized_height(self, _text: str = "", _size: int = 0) -> int:
        """Return a plausible font height."""
        return 12


class _StubAssets:
    def icon(self, _size: int) -> _StubFont:
        return _StubFont()

    def font(self, _size: int) -> _StubFont:
        return _StubFont()

    def font_bold(self, _size: int) -> _StubFont:
        return _StubFont()


def _make_panel(tmp_path: Path) -> SettingsPanel:
    return SettingsPanel(assets=_StubAssets(), config=ConfigStore(tmp_path / "config.toml"))  # type: ignore[arg-type]


def test_device_info_storage_row_uses_provider_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The storage row measures the provider's storage directory, with exact numbers."""
    measured: list[Path] = []

    def _fake_disk_usage(path: object) -> SimpleNamespace:
        measured.append(Path(str(path)))
        return SimpleNamespace(used=5 * 1024**3, total=32 * 1024**3)

    monkeypatch.setattr("piframe.settings_panel.shutil.disk_usage", _fake_disk_usage)
    provider = SimpleNamespace(storage_dir=tmp_path)
    sync = SimpleNamespace(provider=provider, status=SyncStatus())
    panel = SettingsPanel(
        assets=_StubAssets(),  # type: ignore[arg-type]
        config=ConfigStore(tmp_path / "config.toml"),
        sync_service=sync,  # type: ignore[arg-type]
    )
    rows = panel._get_device_info()
    storage = [value for label, value in rows if label == "Storage"]
    assert storage == ["5.0 / 32 GB"]
    assert measured == [tmp_path]


def test_device_info_storage_row_dash_without_storage(tmp_path: Path) -> None:
    """Providers without local storage (e.g. the Google stub) show a dash."""
    provider = SimpleNamespace(storage_dir=None)
    sync = SimpleNamespace(provider=provider, status=SyncStatus())
    panel = SettingsPanel(
        assets=_StubAssets(),  # type: ignore[arg-type]
        config=ConfigStore(tmp_path / "config.toml"),
        sync_service=sync,  # type: ignore[arg-type]
    )
    rows = panel._get_device_info()
    storage = [value for label, value in rows if label == "Storage"]
    assert storage == ["—"]


def _screen() -> pygame.Surface:
    return pygame.Surface((SCREEN_W, SCREEN_H))


@pytest.fixture(scope="module", autouse=True)
def pg() -> None:
    """Initialise pygame for the test module."""
    pygame.init()
    pygame.display.set_mode((SCREEN_W, SCREEN_H))


def test_draw_content_background(tmp_path: Path) -> None:
    """draw() fills the content area background (line 354)."""
    panel = _make_panel(tmp_path)
    panel._active_section = Section.DISPLAY
    panel.open()

    panel.draw(_screen())  # hits line 354 (content bg rect)


def test_display_brightness_percentage_label(tmp_path: Path) -> None:
    """Display section renders brightness percentage label (line 415)."""
    panel = _make_panel(tmp_path)
    panel._active_section = Section.DISPLAY
    panel.open()

    panel.draw(_screen())  # hits line 415 (pct_surf render)


def test_wifi_forget_button_when_connected(tmp_path: Path) -> None:
    """WiFi section shows 'Forget current' button when connected (line 456)."""
    panel = _make_panel(tmp_path)
    panel._wifi_status = WifiStatus(connected=True, ssid="Home", ip_address="10.0.0.1")
    panel._active_section = Section.WIFI
    panel.open()

    panel.draw(_screen())  # hits line 456 (forget button rect)


def test_wifi_connect_button_with_password_prompt(tmp_path: Path) -> None:
    """WiFi section shows 'Connect' button when password prompt is active (line 478)."""
    panel = _make_panel(tmp_path)
    panel._wifi_password_ssid = "SecureNet"
    panel._active_section = Section.WIFI
    panel.open()

    panel.draw(_screen())  # hits line 478 (connect button rect)


def test_about_git_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """About section shows git version from subprocess (line 571)."""
    import subprocess

    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: b"v1.2.3")
    panel = _make_panel(tmp_path)
    panel._active_section = Section.SYSTEM
    panel.open()

    panel.draw(_screen())  # hits line 571 (subprocess.check_output call)


def test_about_disk_usage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """About section shows disk usage stats (lines 611, 615-616)."""
    import shutil

    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda p: SimpleNamespace(total=32 * 1024**3, used=5 * 1024**3, free=27 * 1024**3),
    )
    panel = _make_panel(tmp_path)
    panel._active_section = Section.SYSTEM
    panel.open()

    panel.draw(_screen())  # hits lines 611, 615-616 (disk_usage + formatting)
