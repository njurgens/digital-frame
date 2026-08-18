"""Tests for the app's IPC executor methods (one per JSON-RPC method)."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from piframe.app import App

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.ipc import IpcError


@pytest.fixture(scope="module", autouse=True)
def pg() -> Generator[None]:
    """Initialise pygame for the test module."""
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def make_app(tmp_path: Path) -> App:
    """Build an App instance with mocked dependencies (no IPC server)."""
    from piframe.config_store import ConfigStore
    from piframe.types import AppState, init_events

    init_events()
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("[slideshow]\ninterval = 10\n")

    from piframe.app import App

    app = App.__new__(App)
    app._screen = pygame.display.get_surface()
    app._clock = pygame.time.Clock()
    app._state = AppState.SLIDESHOW
    app._config = ConfigStore(cfg_path)
    app._player = MagicMock()
    app._player.is_paused = False
    app._clock_w = MagicMock()
    app._overlay = MagicMock()
    app._overlay.dismissed = False
    app._settings = MagicMock()
    app._keyboard = MagicMock()
    app._sleep = MagicMock()
    app._backlight = MagicMock()
    app._dialog = None
    app._ipc = None
    app._swipe_start_pos = None
    app._swipe_start_time = None
    app._suppress_next_tap = False
    return app


def test_ipc_state_reports_state(tmp_path: Path) -> None:
    """The state method reports the current app state."""
    app = make_app(tmp_path)
    assert app._ipc_state({}) == {"state": "SLIDESHOW"}


def test_ipc_tap_posts_mouse_events(tmp_path: Path) -> None:
    """Tap posts a down/up pair at the given coordinates."""
    app = make_app(tmp_path)
    assert app._ipc_tap({"x": 10, "y": 20}) == {}


def test_ipc_tap_rejects_missing_and_non_integer_coords(tmp_path: Path) -> None:
    """Tap requires integer x and y params."""
    app = make_app(tmp_path)
    with pytest.raises(IpcError) as exc:
        app._ipc_tap({})
    assert exc.value.code == -32602
    with pytest.raises(IpcError):
        app._ipc_tap({"x": "10", "y": 20})


def test_ipc_swipe_posts_motion_events(tmp_path: Path) -> None:
    """Swipe posts a down, a series of motions, and an up."""
    app = make_app(tmp_path)
    assert app._ipc_swipe({"x": 0, "y": 0, "dx": 100, "dy": 0, "ms": 16}) == {}


def test_ipc_swipe_rejects_missing_coords(tmp_path: Path) -> None:
    """Swipe requires x, y, dx, and dy."""
    app = make_app(tmp_path)
    with pytest.raises(IpcError) as exc:
        app._ipc_swipe({"x": 0, "y": 0})
    assert exc.value.code == -32602


def test_ipc_play_pause_toggles_and_reports(tmp_path: Path) -> None:
    """play_pause toggles the player and reports the new paused state."""
    app = make_app(tmp_path)
    assert app._ipc_play_pause({}) == {"paused": True}
    app._overlay.set_paused.assert_called_with(True)  # type: ignore[union-attr]
    assert app._ipc_play_pause({}) == {"paused": False}


def test_ipc_prev_and_next_drive_the_player(tmp_path: Path) -> None:
    """Prev and next drive the player's navigation."""
    app = make_app(tmp_path)
    assert app._ipc_prev({}) == {}
    app._player.go_back.assert_called_once()  # type: ignore[union-attr]
    assert app._ipc_next({}) == {}
    app._player.skip.assert_called_once()  # type: ignore[union-attr]


def test_ipc_screenshot_saves_the_screen(tmp_path: Path) -> None:
    """Screenshot saves the screen to the given path."""
    app = make_app(tmp_path)
    out = tmp_path / "shot.png"
    assert app._ipc_screenshot({"path": str(out)}) == {}
    assert out.exists()


def test_ipc_screenshot_requires_path(tmp_path: Path) -> None:
    """Screenshot requires a path param."""
    app = make_app(tmp_path)
    with pytest.raises(IpcError) as exc:
        app._ipc_screenshot({})
    assert exc.value.code == -32602


def test_ipc_set_config_updates_config_and_refreshes(tmp_path: Path) -> None:
    """set_config sets the value and refreshes the settings panel."""
    app = make_app(tmp_path)
    assert app._ipc_set_config({"section": "slideshow", "key": "interval", "value": 45}) == {}
    assert app._config.slideshow.interval == 45.0
    app._settings.sync_from_config.assert_called_once()  # type: ignore[union-attr]
    with pytest.raises(IpcError):
        app._ipc_set_config({"section": "slideshow", "key": "interval"})


def test_ipc_set_config_sleep_section_kicks_sleep(tmp_path: Path) -> None:
    """set_config on the sleep section kicks the sleep scheduler."""
    app = make_app(tmp_path)
    app._ipc_set_config({"section": "sleep", "key": "enabled", "value": True})
    app._sleep.kick.assert_called_once()  # type: ignore[union-attr]


def test_ipc_trigger_sync_triggers_the_sync_service(tmp_path: Path) -> None:
    """trigger_sync triggers the sync service."""
    app = make_app(tmp_path)
    app._sync = MagicMock()
    assert app._ipc_trigger_sync({}) == {}
    app._sync.trigger.assert_called_once()
