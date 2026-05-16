import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.widgets.vertical_slider import VerticalSlider


@pytest.fixture(scope="module", autouse=True)
def pygame_init_module():
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


def make_slider(value=50):
    rect = pygame.Rect(100, 100, 40, 200)
    return VerticalSlider(rect=rect, initial_value=value)


def test_drag_from_top_gives_100():
    sl = make_slider(50)
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(120, 100), button=1))
    assert sl.value == 100


def test_drag_from_bottom_gives_0():
    sl = make_slider(50)
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(120, 300), button=1))
    assert sl.value == 0


def test_drag_to_midpoint_gives_50():
    sl = make_slider(0)
    mid_y = sl.rect.top + 11 + (sl.rect.height - 22) // 2
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(120, mid_y), button=1))
    assert abs(sl.value - 50) <= 2


def test_value_clamped_to_range():
    sl = make_slider(50)
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(120, sl.rect.top - 50), button=1))
    assert sl.value == 100
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(120, sl.rect.top - 50), button=1))
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(120, sl.rect.bottom + 50), button=1))
    assert sl.value == 0


def test_on_change_called_during_drag():
    changes = []
    rect = pygame.Rect(100, 100, 40, 200)
    sl = VerticalSlider(rect=rect, initial_value=50, on_change=lambda v: changes.append(v))
    sl.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(120, 150), button=1))
    sl.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(120, 200), rel=(0, 50), buttons=(1, 0, 0)))
    assert len(changes) >= 1
