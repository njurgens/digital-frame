import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import datetime

from piframe.sleep_scheduler import is_sleep_time


def t(h, m):
    return datetime.time(h, m)


def test_non_crossing_inside():
    assert is_sleep_time(t(12, 0), t(9, 0), t(17, 0)) is True


def test_non_crossing_before():
    assert is_sleep_time(t(8, 59), t(9, 0), t(17, 0)) is False


def test_non_crossing_after():
    assert is_sleep_time(t(17, 0), t(9, 0), t(17, 0)) is False


def test_non_crossing_at_boundary_start():
    assert is_sleep_time(t(9, 0), t(9, 0), t(17, 0)) is True


def test_non_crossing_at_boundary_end():
    assert is_sleep_time(t(17, 0), t(9, 0), t(17, 0)) is False


def test_crossing_in_evening():
    assert is_sleep_time(t(23, 0), t(22, 0), t(7, 0)) is True


def test_crossing_in_morning():
    assert is_sleep_time(t(3, 0), t(22, 0), t(7, 0)) is True


def test_crossing_outside():
    assert is_sleep_time(t(10, 0), t(22, 0), t(7, 0)) is False


def test_crossing_at_sleep_boundary():
    assert is_sleep_time(t(22, 0), t(22, 0), t(7, 0)) is True


def test_crossing_at_wake_boundary():
    assert is_sleep_time(t(7, 0), t(22, 0), t(7, 0)) is False


def test_equal_times_returns_false():
    assert is_sleep_time(t(10, 0), t(10, 0), t(10, 0)) is False
