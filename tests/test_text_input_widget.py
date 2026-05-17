import os
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.assets import IC_VISIBILITY, IC_VISIBILITY_OFF
from piframe.widgets.text_input import TextInput


@pytest.fixture(scope="module", autouse=True)
def pygame_init_module():
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def _make_assets():
    assets = MagicMock()
    surf = pygame.Surface((60, 20), pygame.SRCALPHA)
    assets.font.return_value.render.return_value = (surf, surf.get_rect())
    assets.icon.return_value.render.return_value = (surf, surf.get_rect())
    return assets


def test_draw_without_assets_still_draws_border():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), placeholder="pw", password_mode=True, assets=None)
    ti.append("abc")
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)
    screen.fill((0, 0, 0, 0))

    ti.draw(screen)

    assert screen.get_at((100, 0))[:3] == (255, 255, 255)


def test_draw_placeholder_uses_caption_colour():
    assets = _make_assets()
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), placeholder="pw", assets=assets)
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)

    ti.draw(screen)

    assert assets.font.return_value.render.call_args[0][0] == "pw"


def test_draw_password_mask_uses_supported_bullet():
    assets = _make_assets()
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), password_mode=True, assets=assets)
    ti.append("abc")
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)

    ti.draw(screen)

    rendered = [c.args[0] for c in assets.font.return_value.render.call_args_list]
    assert "•••" in rendered
    assert "●●●" not in rendered
    assert "abc" not in rendered


def test_draw_password_show_text_renders_plaintext():
    assets = _make_assets()
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), password_mode=True, assets=assets)
    ti.append("abc")
    ti._show_text = True
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)

    ti.draw(screen)

    rendered = [c.args[0] for c in assets.font.return_value.render.call_args_list]
    assert "abc" in rendered


def test_draw_password_icon_uses_visibility_off_when_masked():
    assets = _make_assets()
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), password_mode=True, assets=assets)
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)

    ti.draw(screen)

    assert assets.icon.return_value.render.call_args[0][0] == IC_VISIBILITY_OFF


def test_draw_password_icon_uses_visibility_when_shown():
    assets = _make_assets()
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), password_mode=True, assets=assets)
    ti._show_text = True
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)

    ti.draw(screen)

    assert assets.icon.return_value.render.call_args[0][0] == IC_VISIBILITY


def test_handle_event_eye_toggle_consumes_and_toggles():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), password_mode=True, assets=_make_assets())
    eye = ti._eye_rect().center
    evt = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=eye, button=1)

    assert ti.handle_event(evt) is True
    assert ti._show_text is True
    assert ti.handle_event(evt) is True
    assert ti._show_text is False


def test_handle_event_focus_inside_and_outside():
    focused = []
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), assets=_make_assets(), on_focus=lambda: focused.append(True))

    inside = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(50, 20), button=1)
    outside = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(250, 20), button=1)

    assert ti.handle_event(inside) is True
    assert ti._focused is True
    assert focused == [True]
    assert ti.handle_event(outside) is False
    assert ti._focused is False


def test_on_change_paths_and_text_property():
    changes = []
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), assets=_make_assets(), on_change=changes.append)
    ti.append("a")
    ti.append("b")
    ti.backspace()
    ti.clear()
    assert ti.text == ""
    assert changes == ["a", "ab", "a", ""]


def test_set_focused_affects_cursor_draw_path():
    assets = _make_assets()
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), assets=assets)
    ti.append("abc")
    ti.set_focused(True)
    screen = pygame.Surface((220, 60), pygame.SRCALPHA)

    ti.draw(screen)

    rendered = [c.args[0] for c in assets.font.return_value.render.call_args_list]
    assert rendered.count("abc") >= 2


def test_handle_event_without_pos_is_not_consumed():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), assets=_make_assets())
    evt = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1)
    assert ti.handle_event(evt) is False
