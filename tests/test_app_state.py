"""Tests for app state transitions and event handling."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from queue import SimpleQueue
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from piframe.app import App

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest


@pytest.fixture(scope="module", autouse=True)
def pg() -> Generator[None]:
    """Initialise pygame for the test module."""
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def make_app(tmp_path: Path) -> App:
    """Build an App instance with mocked dependencies."""
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
    app._harness_queue = SimpleQueue()
    app._swipe_start_pos = None
    app._swipe_start_time = None
    app._suppress_next_tap = False
    app._args = MagicMock(test_harness=False)
    return app


def test_slideshow_tap_transitions_to_overlay(tmp_path: Path) -> None:
    """Slideshow tap transitions to overlay."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    assert app._state == AppState.SLIDESHOW
    app._dispatch_tap((640, 400))
    assert app._state == AppState.OVERLAY
    app._overlay.show.assert_called()  # type: ignore[union-attr]


def test_overlay_tap_outside_controls_returns_to_slideshow(tmp_path: Path) -> None:
    """Overlay tap outside controls returns to slideshow."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = None  # type: ignore[union-attr]
    app._dispatch_tap((640, 400))
    assert app._state == AppState.SLIDESHOW


def test_overlay_dismissed_flag_returns_to_slideshow(tmp_path: Path) -> None:
    """Overlay dismissed flag returns to slideshow."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.dismissed = True
    app._update(0.016)
    assert app._state == AppState.SLIDESHOW


def test_overlay_settings_action_transitions_to_settings(tmp_path: Path) -> None:
    """Overlay settings action transitions to settings."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = "settings"  # type: ignore[union-attr]
    app._dispatch_tap((1240, 33))
    assert app._state == AppState.SETTINGS
    app._settings.open.assert_called_once()  # type: ignore[union-attr]


def test_play_pause_tap_toggles_player(tmp_path: Path) -> None:
    """Play pause tap toggles player."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = "play_pause"  # type: ignore[union-attr]
    app._player.is_paused = False
    app._dispatch_tap((640, 400))
    assert app._player.is_paused is True
    app._overlay.set_paused.assert_called_once_with(True)  # type: ignore[union-attr]


def test_on_focus_text_transitions_to_keyboard(tmp_path: Path) -> None:
    """On focus text transitions to keyboard."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.SETTINGS
    field = MagicMock()
    app._on_focus_text(field)
    assert app._state == AppState.KEYBOARD
    app._keyboard.attach.assert_called_once_with(field)  # type: ignore[union-attr]


def test_keyboard_done_returns_to_settings(tmp_path: Path) -> None:
    """Keyboard done returns to settings."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.KEYBOARD
    app._on_keyboard_done()
    assert app._state == AppState.SETTINGS


def test_sleeping_tap_wakes_to_overlay(tmp_path: Path) -> None:
    """Sleeping tap wakes to overlay."""
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.SLEEPING
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(640, 400), button=1))
    app._process_pygame_events()
    assert app._state == AppState.OVERLAY
    app._overlay.show.assert_called_once()  # type: ignore[union-attr]
    app._backlight.set_brightness.assert_called_once_with(app._config.display.brightness)  # type: ignore[union-attr]
    app._sleep.set_grace.assert_called_once()  # type: ignore[union-attr]


def test_pointer_up_diagonal_drag_does_not_dispatch_tap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up diagonal drag does not dispatch tap."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (100, 100)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.2)

    app._classify_pointer_up((250, 180))

    app._dispatch_tap.assert_not_called()
    app._player.skip.assert_not_called()  # type: ignore[union-attr]
    app._player.go_back.assert_not_called()  # type: ignore[union-attr]


def test_pointer_up_allows_diagonal_horizontal_swipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up allows diagonal horizontal swipe."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (400, 300)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.2)

    app._classify_pointer_up((180, 341))

    app._player.skip.assert_called_once()  # type: ignore[union-attr]
    app._dispatch_tap.assert_not_called()


def test_pointer_up_short_movement_dispatches_tap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up short movement dispatches tap."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (100, 100)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.2)

    app._classify_pointer_up((110, 112))

    app._dispatch_tap.assert_called_once_with((110, 112))


def test_pointer_up_without_start_tracking_is_noop(tmp_path: Path) -> None:
    """Pointer up without start tracking is noop."""
    app = make_app(tmp_path)
    app._swipe_start_pos = None
    app._swipe_start_time = None
    app._dispatch_tap = MagicMock()

    app._classify_pointer_up((640, 400))

    app._dispatch_tap.assert_not_called()


def test_pointer_up_accepts_swipe_at_slope_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up accepts swipe at slope boundary."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (100, 100)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.2)

    app._classify_pointer_up((161, 130))  # dx=61, dy=30 => dy <= dx*0.5

    app._player.go_back.assert_called_once()  # type: ignore[union-attr]
    app._dispatch_tap.assert_not_called()


def test_pointer_up_rejects_swipe_just_over_slope_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up rejects swipe just over slope boundary."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (100, 100)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.2)

    app._classify_pointer_up((161, 131))  # dx=61, dy=31 => dy > dx*0.5

    app._player.go_back.assert_not_called()  # type: ignore[union-attr]
    app._dispatch_tap.assert_not_called()


def test_pointer_up_tap_distance_boundary_dispatches_tap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up tap distance boundary dispatches tap."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (100, 100)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.2)

    app._classify_pointer_up((120, 100))  # distance == 20

    app._dispatch_tap.assert_called_once_with((120, 100))


def test_pointer_up_rejects_swipe_at_elapsed_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pointer up rejects swipe at elapsed boundary."""
    app = make_app(tmp_path)
    app._swipe_start_pos = (100, 100)
    app._swipe_start_time = 10.0
    app._dispatch_tap = MagicMock()
    monkeypatch.setattr("piframe.app.time.monotonic", lambda: 10.4)

    app._classify_pointer_up((180, 120))

    app._player.go_back.assert_not_called()  # type: ignore[union-attr]
    app._dispatch_tap.assert_not_called()
