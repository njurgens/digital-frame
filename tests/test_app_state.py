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
    app._overlay = MagicMock()
    app._overlay.dismissed = False
    app._harness_queue = SimpleQueue()
    app._swipe_start_pos = None
    app._swipe_start_time = None
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


def test_play_pause_tap_toggles_player(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.OVERLAY
    app._overlay.on_tap.return_value = "play_pause"
    app._player.is_paused = False
    app._dispatch_tap((640, 400))
    assert app._player.is_paused is True


def test_sleeping_tap_wakes_to_overlay(tmp_path):
    app = make_app(tmp_path)
    from piframe.types import AppState

    app._state = AppState.SLEEPING
    app._overlay.show()
    app._state = AppState.OVERLAY
    assert app._state == AppState.OVERLAY
