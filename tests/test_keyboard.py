import os
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.keyboard import IC_BACKSPACE, IC_SHIFT, IC_SHIFT_LOCK, Keyboard


@pytest.fixture(scope="module", autouse=True)
def pygame_init():
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def _make_assets():
    assets = MagicMock()
    text_surf = pygame.Surface((24, 24), pygame.SRCALPHA)
    icon_surf = pygame.Surface((24, 24), pygame.SRCALPHA)
    assets.font.return_value.render.return_value = (text_surf, text_surf.get_rect())
    assets.icon.return_value.render.return_value = (icon_surf, icon_surf.get_rect())
    return assets


def test_keyboard_draw_uses_icon_font_for_shift_and_backspace():
    assets = _make_assets()
    kb = Keyboard(assets)
    kb.attach(MagicMock())
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)

    kb.draw(screen)

    icon_calls = [call.args[0] for call in assets.icon.return_value.render.call_args_list]
    assert IC_SHIFT in icon_calls
    assert IC_BACKSPACE in icon_calls
    assert "⇧" not in icon_calls
    assert "⌫" not in icon_calls


def test_keyboard_draw_uses_shift_lock_icon_when_shift_enabled():
    assets = _make_assets()
    kb = Keyboard(assets)
    kb.attach(MagicMock())
    kb._shift = True
    screen = pygame.Surface((1280, 800), pygame.SRCALPHA)

    kb.draw(screen)

    icon_calls = [call.args[0] for call in assets.icon.return_value.render.call_args_list]
    assert IC_SHIFT_LOCK in icon_calls
    assert "⇪" not in icon_calls


def test_attach_and_detach_manage_visibility_state():
    kb = Keyboard(_make_assets())
    target = MagicMock()
    kb.attach(target)
    assert kb.is_visible is True
    assert kb._target is target
    kb.detach()
    assert kb.is_visible is False
    assert kb._target is None


def test_handle_event_returns_false_when_hidden():
    kb = Keyboard(_make_assets())
    evt = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(10, 10), button=1)
    assert kb.handle_event(evt) is False


def test_handle_event_mouse_down_selects_key_and_mouse_up_emits():
    kb = Keyboard(_make_assets())
    target = MagicMock()
    kb.attach(target)
    key_rect = kb._key_rects[0][0]
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=key_rect.center, button=1)
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, pos=key_rect.center, button=1)
    assert kb.handle_event(down) is True
    assert kb._active_key == (0, 0)
    assert kb.handle_event(up) is True
    target.append.assert_called_once_with("q")


def test_handle_event_mouse_down_outside_keys_is_not_consumed():
    kb = Keyboard(_make_assets())
    kb.attach(MagicMock())
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(2, 2), button=1)
    assert kb.handle_event(down) is False


def test_emit_backspace_space_done_and_shift_paths():
    on_done = MagicMock()
    kb = Keyboard(_make_assets(), on_done=on_done)
    target = MagicMock()
    kb.attach(target)

    kb._emit(2, 8)
    target.backspace.assert_called_once()

    kb._emit(3, 1)
    target.append.assert_called_with(" ")

    kb._emit(2, 0)
    assert kb._shift is True

    kb._emit(3, 2)
    assert kb.is_visible is False
    on_done.assert_called_once()


def test_emit_layer_switches_and_shifted_character():
    kb = Keyboard(_make_assets())
    target = MagicMock()
    kb.attach(target)

    kb._emit(3, 0)
    assert kb._layer == "numeric"
    kb._emit(2, 0)
    assert kb._layer == "extended"
    kb._emit(3, 0)
    assert kb._layer == "alpha"

    kb._shift = True
    kb._emit(0, 0)
    target.append.assert_called_with("Q")
    assert kb._shift is False
