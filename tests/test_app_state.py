import os
from pathlib import Path
from queue import SimpleQueue
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest


@pytest.fixture(scope="module", autouse=True)
def pg():
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def make_app(tmp_path: Path):
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
    app._args = MagicMock(test_harness=False, mock_wifi=False)
    return app


def test_slideshow_tap_transitions_to_overlay(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    assert app._state == AppState.SLIDESHOW
    app._dispatch_tap((640, 400))
    assert app._state == AppState.OVERLAY
    app._overlay.show.assert_called()


def test_overlay_tap_outside_controls_returns_to_slideshow(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = None
    app._dispatch_tap((640, 400))
    assert app._state == AppState.SLIDESHOW


def test_overlay_dismissed_flag_returns_to_slideshow(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.dismissed = True
    app._update(0.016)
    assert app._state == AppState.SLIDESHOW


def test_overlay_settings_action_transitions_to_settings(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = "settings"
    app._dispatch_tap((1240, 33))
    assert app._state == AppState.SETTINGS
    app._settings.open.assert_called_once()


def test_play_pause_tap_toggles_player(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = "play_pause"
    app._player.is_paused = False
    app._dispatch_tap((640, 400))
    assert app._player.is_paused is True
    app._overlay.set_paused.assert_called_once_with(True)


def test_on_focus_text_transitions_to_keyboard(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.SETTINGS
    field = MagicMock()
    app._on_focus_text(field)
    assert app._state == AppState.KEYBOARD
    app._keyboard.attach.assert_called_once_with(field)


def test_keyboard_done_returns_to_settings(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.KEYBOARD
    app._on_keyboard_done()
    assert app._state == AppState.SETTINGS


def test_sleeping_tap_wakes_to_overlay(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.SLEEPING
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(640, 400), button=1))
    app._process_pygame_events()
    assert app._state == AppState.OVERLAY
    app._overlay.show.assert_called_once()
    app._backlight.set_brightness.assert_called_once_with(app._config.display.brightness)
    app._sleep.set_grace.assert_called_once()
