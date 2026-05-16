import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest
from unittest.mock import MagicMock

from piframe.widgets.vertical_slider import VerticalSlider
from piframe.widgets.segmented_control import SegmentedControl
from piframe.widgets.scroll_picker import ScrollPicker
from piframe.widgets.confirm_dialog import ConfirmDialog
from piframe.widgets.text_input import TextInput
from piframe.widgets.time_picker import TimePicker
from piframe.widgets.toggle import Toggle
from piframe.widgets.wifi_list_item import WifiListItem
from piframe.types import WifiNetwork


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


def make_mock_assets():
    mock_assets = MagicMock()
    surf = pygame.Surface((60, 20))
    mock_assets.font.return_value.render.return_value = (surf, pygame.Rect(0, 0, 60, 20))
    mock_assets.font_bold.return_value.render.return_value = (surf, pygame.Rect(0, 0, 60, 20))
    return mock_assets


def test_scroll_picker_drag_scroll():
    rect = pygame.Rect(100, 100, 200, 308)
    items = [f"Item {i}" for i in range(30)]
    assets = make_mock_assets()
    sp = ScrollPicker(rect=rect, items=items, selected=0, assets=assets)
    initial_offset = sp._scroll_offset
    sp.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(200, 200), button=1))
    sp.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(200, 156), rel=(0, -44), buttons=(1, 0, 0)))
    assert sp._scroll_offset > initial_offset


def test_scroll_picker_snap_on_release():
    rect = pygame.Rect(100, 100, 200, 308)
    items = [f"TZ {i}" for i in range(50)]
    assets = make_mock_assets()
    sp = ScrollPicker(rect=rect, items=items, selected=5, assets=assets)
    sp.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(200, 200), button=1))
    sp.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(200, 178), rel=(0, -22), buttons=(1, 0, 0)))
    sp.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(200, 178), button=1))
    assert sp._scroll_offset == int(sp._scroll_offset)


def test_scroll_picker_clamp_min():
    rect = pygame.Rect(100, 100, 200, 308)
    items = [f"Item {i}" for i in range(10)]
    assets = make_mock_assets()
    sp = ScrollPicker(rect=rect, items=items, selected=0, assets=assets)
    sp.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(200, 200), button=1))
    sp.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=(200, 500), rel=(0, 300), buttons=(1, 0, 0)))
    assert sp._scroll_offset >= 0


def test_time_picker_open_done_updates_time():
    changes = []
    assets = make_mock_assets()
    tp = TimePicker(
        rect=pygame.Rect(100, 100, 168, 44),
        initial_hour=10,
        initial_minute=30,
        assets=assets,
        on_change=lambda h, m: changes.append((h, m)),
    )
    tp.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(110, 110), button=1))
    tp._hour_picker.set_selected(12)
    tp._min_picker.set_selected(45)
    done_pos = (tp._popup_rect.right - 24, tp._popup_rect.y + 24)
    tp.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=done_pos, button=1))
    assert changes == [(12, 45)]


def test_text_input_append():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44))
    ti.append("h")
    ti.append("i")
    assert ti.text == "hi"


def test_text_input_backspace():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44))
    ti.append("hello")
    ti.backspace()
    assert ti.text == "hell"


def test_text_input_backspace_empty():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44))
    ti.backspace()
    assert ti.text == ""


def test_text_input_on_change_callback():
    changes = []
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), on_change=changes.append)
    ti.append("x")
    assert changes == ["x"]


def test_text_input_password_mode():
    ti = TextInput(rect=pygame.Rect(0, 0, 200, 44), password_mode=True)
    ti.append("abc")
    assert ti._password_mode is True
    assert ti.text == "abc"


def test_text_input_focus():
    focused = []
    ti = TextInput(rect=pygame.Rect(100, 100, 200, 44), on_focus=lambda: focused.append(True))
    ti.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(150, 122), button=1))
    assert ti._focused is True
    assert focused == [True]


def test_confirm_dialog_cancel():
    cancelled = []
    dlg = ConfirmDialog(
        title="Delete?",
        body="This cannot be undone.",
        on_cancel=lambda: cancelled.append(True),
        on_confirm=lambda: None,
    )
    dlg.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            pos=(dlg._cancel_rect.centerx, dlg._cancel_rect.centery),
            button=1,
        )
    )
    assert cancelled == [True]


def test_confirm_dialog_confirm():
    confirmed = []
    dlg = ConfirmDialog(
        title="Delete?",
        body="This cannot be undone.",
        on_confirm=lambda: confirmed.append(True),
        on_cancel=lambda: None,
    )
    dlg.handle_event(
        pygame.event.Event(
            pygame.MOUSEBUTTONDOWN,
            pos=(dlg._confirm_rect.centerx, dlg._confirm_rect.centery),
            button=1,
        )
    )
    assert confirmed == [True]


def test_confirm_dialog_outside_cancels():
    cancelled = []
    dlg = ConfirmDialog(
        title="Test",
        body="Body",
        on_cancel=lambda: cancelled.append(True),
        on_confirm=lambda: None,
    )
    dlg.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(0, 0), button=1))
    assert cancelled == [True]


def test_wifi_list_item_tap_callback():
    net = WifiNetwork(ssid="TestNet", security="WPA2", signal=75)
    tapped = []
    item = WifiListItem(
        rect=pygame.Rect(200, 100, 800, 56),
        network=net,
        on_tap=lambda n: tapped.append(n),
    )
    item.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(400, 128), button=1))
    item.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=(400, 128), button=1))
    assert tapped == [net]


def test_wifi_network_signal_level():
    assert WifiNetwork("x", "", 90).signal_level == 2
    assert WifiNetwork("x", "", 50).signal_level == 1
    assert WifiNetwork("x", "", 10).signal_level == 0
