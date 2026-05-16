import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from unittest.mock import mock_open, patch

from piframe.backlight import BACKLIGHT_PATH, BacklightController


def test_set_brightness_0_writes_0():
    ctrl = BacklightController()
    m = mock_open()
    with patch("builtins.open", m):
        ctrl.set_brightness(0)
    m.assert_called_once_with(BACKLIGHT_PATH, "w")
    m().write.assert_called_once_with("0\n")


def test_set_brightness_100_writes_255():
    ctrl = BacklightController()
    m = mock_open()
    with patch("builtins.open", m):
        ctrl.set_brightness(100)
    m().write.assert_called_once_with("255\n")


def test_set_brightness_72_writes_184():
    ctrl = BacklightController()
    m = mock_open()
    with patch("builtins.open", m):
        ctrl.set_brightness(72)
    written = m().write.call_args[0][0]
    assert written == f"{round(72 / 100 * 255)}\n"


def test_set_brightness_clamp_negative():
    ctrl = BacklightController()
    m = mock_open()
    with patch("builtins.open", m):
        ctrl.set_brightness(-1)
    m().write.assert_called_once_with("0\n")


def test_set_brightness_clamp_over_100():
    ctrl = BacklightController()
    m = mock_open()
    with patch("builtins.open", m):
        ctrl.set_brightness(101)
    m().write.assert_called_once_with("255\n")


def test_set_brightness_no_redundant_write():
    ctrl = BacklightController()
    m = mock_open()
    with patch("builtins.open", m):
        ctrl.set_brightness(50)
        ctrl.set_brightness(50)
    assert m().write.call_count == 1


def test_get_brightness_oserror_returns_50():
    ctrl = BacklightController()
    with patch("builtins.open", side_effect=OSError):
        result = ctrl.get_brightness()
    assert result == 50
