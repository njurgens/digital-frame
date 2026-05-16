import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.widgets.vertical_slider import VerticalSlider
from piframe.widgets.segmented_control import SegmentedControl
from piframe.widgets.toggle import Toggle


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


def test_toggle_tap_flips_state():
    rect = pygame.Rect(100, 100, 50, 28)
    t = Toggle(rect=rect, initial=False)
    assert t._on is False
    t.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(125, 114), button=1))
    assert t._on is True


def test_toggle_tap_fires_callback():
    results = []
    rect = pygame.Rect(100, 100, 50, 28)
    t = Toggle(rect=rect, initial=False, on_change=lambda v: results.append(v))
    t.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(125, 114), button=1))
    assert results == [True]


def test_segmented_control_tap_sets_active():
    rect = pygame.Rect(100, 100, 300, 36)
    sc = SegmentedControl(rect=rect, segments=["A", "B", "C"], selected=0)
    sc.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(250, 118), button=1))
    assert sc._selected == 1


def test_segmented_control_callback_fires():
    results = []
    rect = pygame.Rect(0, 0, 300, 36)
    sc = SegmentedControl(
        rect=rect,
        segments=["X", "Y", "Z"],
        selected=0,
        on_change=lambda i, s: results.append((i, s)),
    )
    sc.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(250, 18), button=1))
    assert results[0][0] == 2
    assert results[0][1] == "Z"
