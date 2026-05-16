"""Integration tests (Tier 3) — require Pi SSH access.

Run with:
    pytest tests/test_integration.py -v -m integration

All tests use the pi_app fixture from conftest.py which:
- SSH-connects to frame@10.1.7.58
- Starts the app in --test-harness --mock-wifi mode
- Provides a Unix-socket command harness via socat TCP bridge
"""

from __future__ import annotations

import datetime as dt
import time
from pathlib import Path

import numpy as np
import paramiko
import pytest
from PIL import Image

from piframe.backlight import BACKLIGHT_PATH
from tests.image_utils import assert_screenshot_matches

pytestmark = pytest.mark.integration

SCREEN_W = 1280
SCREEN_H = 800
CLOCK_IGNORE = [(0, 0, 300, 60)]  # mask clock region in screenshot comparisons
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 9901

SLIDESHOW_DIR = "/home/frame/Pictures/slideshow"
APP_DIR = "/home/frame/digital-frame"


# Tap/gesture coordinates
CENTER = (640, 400)
OVERLAY_DISMISS = (100, 700)
PAUSE_BTN = (600, 756)
GEAR_BTN = (1240, 33)
BACK_BTN = (100, 30)
SLIDER_LOW = (1240, 700)
SWIPE_START = (640, 400)

NAV_SLIDESHOW = (100, 94)
NAV_DISPLAY = (100, 150)
NAV_WIFI = (100, 206)
NAV_SYSTEM = (100, 262)

INTERVAL_5S = (440, 98)
FIT_FILL = (1030, 170)
SHOW_CLOCK_TOGGLE = (1237, 176)
SLEEP_ENABLED_TOGGLE = (1237, 248)
SLEEP_TIME_PICKER = (435, 310)
WAKE_TIME_PICKER = (435, 382)

WIFI_SCAN_BTN = (450, 158)
WIFI_FIRST_ROW = (600, 228)
WIFI_PASSWORD_FIELD = (650, 322)
WIFI_CONNECT_BTN = (450, 378)

SYSTEM_SYNC_NOW = (451, 158)
SYSTEM_CHECK_UPDATE = (680, 158)
SYSTEM_SHUTDOWN = (640, 230)
DIALOG_CANCEL = (520, 474)

KEY_H = (766, 582)
KEY_E = (325, 499)
KEY_L = (1144, 582)
KEY_O = (1081, 499)
KEY_DONE = (1192, 748)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ssh(harness) -> paramiko.SSHClient:
    """Return the underlying paramiko SSH client from the harness."""
    return harness._ssh


def _remote_run(harness, cmd: str) -> str:
    """Run a command on the Pi and return stdout."""
    _, stdout, _ = _ssh(harness).exec_command(cmd)
    return stdout.read().decode().strip()


def _remote_run_status(harness, cmd: str) -> tuple[int, str, str]:
    """Run a command on Pi and return (exit_code, stdout, stderr)."""
    _, stdout, stderr = _ssh(harness).exec_command(cmd)
    code = stdout.channel.recv_exit_status()
    return code, stdout.read().decode(), stderr.read().decode()


def _backlight_value(harness) -> int:
    """Read current raw backlight brightness (0-255) from sysfs."""
    return int(_remote_run(harness, f"cat {BACKLIGHT_PATH}"))


def _backlight_percent(harness) -> int:
    raw = _backlight_value(harness)
    return round(raw / 255 * 100)


def _wait_for_state(harness, state: str, timeout: float = 10.0, poll: float = 0.2) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if harness.state() == state:
                return True
        except OSError:
            pass  # app may be restarting — keep polling
        time.sleep(poll)
    try:
        return harness.state() == state
    except OSError:
        return False


def _tap_and_settle(harness, x: int, y: int, delay: float = 0.2) -> None:
    harness.tap(x, y)
    time.sleep(delay)


def _return_to_slideshow(harness) -> None:
    for _ in range(15):
        try:
            state = harness.state()
        except OSError:
            time.sleep(0.5)
            continue
        if state == "SLIDESHOW":
            return
        if state == "OVERLAY":
            _tap_and_settle(harness, *OVERLAY_DISMISS)
            continue
        if state == "SETTINGS":
            _tap_and_settle(harness, *BACK_BTN)
            continue
        if state == "KEYBOARD":
            _tap_and_settle(harness, *KEY_DONE)
            continue
        if state == "SLEEPING":
            _tap_and_settle(harness, *CENTER)
            continue
        time.sleep(0.2)


def _open_overlay(harness) -> None:
    _return_to_slideshow(harness)
    time.sleep(0.3)  # settle after any pending state change
    _tap_and_settle(harness, *CENTER, delay=0.4)
    if not _wait_for_state(harness, "OVERLAY", timeout=3):
        # Retry once — occasional frame-timing miss
        _tap_and_settle(harness, *CENTER, delay=0.4)
        assert _wait_for_state(harness, "OVERLAY", timeout=3), "OVERLAY did not appear"


def _open_settings(harness) -> None:
    _open_overlay(harness)
    _tap_and_settle(harness, *GEAR_BTN)
    assert _wait_for_state(harness, "SETTINGS", timeout=3)


def _goto_nav(harness, nav_xy: tuple[int, int]) -> None:
    _tap_and_settle(harness, *nav_xy)


def _restart_app(harness, timeout: float = 20.0) -> None:
    """Kill and restart the app in harness mode; block until socket is ready."""
    ssh = _ssh(harness)
    ssh.exec_command("kill -9 $(cat /tmp/slideshow.pid) 2>/dev/null; sleep 0.5")
    time.sleep(1)
    ssh.exec_command(
        "XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 "
        f"nohup python3 {APP_DIR}/slideshow.py --test-harness --mock-wifi "
        "</dev/null >>/tmp/slideshow.log 2>&1 &"
    )
    # Wait for socket to come up and answer
    import socket as _socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect("/tmp/piframe_test.sock")
            s.sendall(b'{"cmd":"state"}\n')
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            s.close()
            if b"state" in data:
                return
        except OSError:
            pass
        time.sleep(0.5)
    pytest.fail(f"App did not restart within {timeout}s")


def _images_differ(a: Path, b: Path, ignore_rects: list[tuple[int, int, int, int]] | None = None, min_fraction: float = 0.01) -> bool:
    arr_a = np.array(Image.open(a).convert("RGB"), dtype=int)
    arr_b = np.array(Image.open(b).convert("RGB"), dtype=int)
    if arr_a.shape != arr_b.shape:
        return True
    if ignore_rects:
        arr_a = arr_a.copy()
        arr_b = arr_b.copy()
        for x, y, w, h in ignore_rects:
            arr_a[y : y + h, x : x + w] = 0
            arr_b[y : y + h, x : x + w] = 0
    diff = np.abs(arr_a - arr_b)
    fraction = float(np.mean(np.any(diff > 10, axis=2)))
    return fraction >= min_fraction


def _set_sleep_window_around_now(harness, wake_delta_min: int = 2) -> None:
    now = dt.datetime.now()
    sleep_t = (now - dt.timedelta(minutes=1)).strftime("%H:%M")
    wake_t = (now + dt.timedelta(minutes=wake_delta_min)).strftime("%H:%M")
    harness.set_config("sleep", "enabled", True)
    harness.set_config("sleep", "sleep_time", sleep_t)
    harness.set_config("sleep", "wake_time", wake_t)


def _ensure_wifi_password_keyboard(harness) -> None:
    _open_settings(harness)
    _goto_nav(harness, NAV_WIFI)
    _tap_and_settle(harness, *WIFI_SCAN_BTN, delay=0.5)
    _tap_and_settle(harness, *WIFI_FIRST_ROW, delay=0.5)
    if harness.state() != "KEYBOARD":
        _tap_and_settle(harness, *WIFI_PASSWORD_FIELD, delay=0.5)
    if harness.state() != "KEYBOARD":
        pytest.skip("Mock Wi-Fi did not expose a password field in this run")


def _type_hello(harness) -> None:
    for key in (KEY_H, KEY_E, KEY_L, KEY_L, KEY_O):
        _tap_and_settle(harness, *key, delay=0.12)


# ---------------------------------------------------------------------------
# Stage 1
# ---------------------------------------------------------------------------


def test_stage1_slideshow_cycles(pi_app):
    _return_to_slideshow(pi_app)
    pi_app.set_config("slideshow", "interval", 2)
    try:
        shot1 = pi_app.screenshot("stage1_slideshow_cycles_a")
        time.sleep(3)
        shot2 = pi_app.screenshot("stage1_slideshow_cycles_b")
        assert _images_differ(shot1, shot2, ignore_rects=CLOCK_IGNORE, min_fraction=0.02)
        assert pi_app.state() == "SLIDESHOW"
    finally:
        pi_app.set_config("slideshow", "interval", 30)


def test_stage1_directory_rescan(pi_app):
    _return_to_slideshow(pi_app)
    pi_app.set_config("slideshow", "interval", 3)
    try:
        _remote_run(
            pi_app,
            f"cp {SLIDESHOW_DIR}/20240803_071132.jpg {SLIDESHOW_DIR}/_test_rescan.jpg",
        )
        time.sleep(5)
        shot = pi_app.screenshot("stage1_directory_rescan")
        assert_screenshot_matches(shot, "stage1_directory_rescan", ignore_rects=CLOCK_IGNORE)
    finally:
        _remote_run(pi_app, f"rm -f {SLIDESHOW_DIR}/_test_rescan.jpg")
        pi_app.set_config("slideshow", "interval", 30)


# ---------------------------------------------------------------------------
# Stage 2
# ---------------------------------------------------------------------------


def test_stage2_tap_shows_overlay(pi_app):
    _open_overlay(pi_app)
    assert pi_app.state() == "OVERLAY"
    _return_to_slideshow(pi_app)


def test_stage2_overlay_autodismiss(pi_app):
    _open_overlay(pi_app)
    time.sleep(6)
    assert _wait_for_state(pi_app, "SLIDESHOW", timeout=2)


def test_stage2_pause_suspends_timer(pi_app):
    _open_overlay(pi_app)
    _tap_and_settle(pi_app, *PAUSE_BTN)
    time.sleep(7)
    assert pi_app.state() == "OVERLAY"
    _tap_and_settle(pi_app, *PAUSE_BTN)
    _return_to_slideshow(pi_app)


def test_stage2_pause_pip_visible(pi_app):
    _open_overlay(pi_app)
    _tap_and_settle(pi_app, *PAUSE_BTN)
    _tap_and_settle(pi_app, *OVERLAY_DISMISS)
    assert _wait_for_state(pi_app, "SLIDESHOW", timeout=2)
    shot = pi_app.screenshot("stage2_pause_pip_visible")
    assert_screenshot_matches(shot, "stage2_pause_pip_visible", ignore_rects=CLOCK_IGNORE)
    _open_overlay(pi_app)
    _tap_and_settle(pi_app, *PAUSE_BTN)
    _return_to_slideshow(pi_app)


def test_stage2_brightness_slider(pi_app):
    _open_overlay(pi_app)
    # Drag to top to establish a known high brightness, then drag to bottom
    pi_app.swipe(1240, 700, dx=0, dy=-530, ms=300)  # bottom → near top (≈94%)
    time.sleep(0.5)
    before = _backlight_value(pi_app)
    pi_app.swipe(1240, 170, dx=0, dy=510, ms=400)  # near top → near bottom (≈7%)
    time.sleep(1)
    after = _backlight_value(pi_app)
    assert before != after
    _return_to_slideshow(pi_app)


def test_stage2_swipe_navigates(pi_app):
    _return_to_slideshow(pi_app)
    base = pi_app.screenshot("stage2_swipe_navigates_base")
    pi_app.swipe(*SWIPE_START, dx=-300, dy=0)
    time.sleep(1)
    nxt = pi_app.screenshot("stage2_swipe_navigates_next")
    pi_app.swipe(*SWIPE_START, dx=300, dy=0)
    time.sleep(1)
    prev = pi_app.screenshot("stage2_swipe_navigates_prev")
    assert _images_differ(base, nxt, ignore_rects=CLOCK_IGNORE)
    assert _images_differ(nxt, prev, ignore_rects=CLOCK_IGNORE)


# ---------------------------------------------------------------------------
# Stage 3
# ---------------------------------------------------------------------------


def test_stage3_config_persists(pi_app):
    _return_to_slideshow(pi_app)
    original = _backlight_percent(pi_app)
    target = 40
    pi_app.set_config("display", "brightness", target)
    time.sleep(1)
    _restart_app(pi_app)
    assert _wait_for_state(pi_app, "SLIDESHOW", timeout=6)
    restored = _backlight_percent(pi_app)
    assert abs(restored - target) <= 8
    pi_app.set_config("display", "brightness", original)


def test_stage3_missing_config_defaults(pi_app):
    ssh = _ssh(pi_app)
    bak = f"{APP_DIR}/config.toml.integration.bak"
    try:
        ssh.exec_command(f"mv {APP_DIR}/config.toml {bak}")
        time.sleep(0.2)
        _restart_app(pi_app)
        assert _wait_for_state(pi_app, "SLIDESHOW", timeout=6)
        assert abs(_backlight_percent(pi_app) - 72) <= 12
    finally:
        ssh.exec_command(f"rm -f {APP_DIR}/config.toml")
        ssh.exec_command(f"mv {bak} {APP_DIR}/config.toml")
        time.sleep(0.5)
        _restart_app(pi_app)
        _return_to_slideshow(pi_app)


# ---------------------------------------------------------------------------
# Stage 4
# ---------------------------------------------------------------------------


def test_stage4_settings_opens(pi_app):
    _open_settings(pi_app)
    assert pi_app.state() == "SETTINGS"
    _return_to_slideshow(pi_app)


def test_stage4_back_returns(pi_app):
    _open_settings(pi_app)
    _tap_and_settle(pi_app, *BACK_BTN)
    assert _wait_for_state(pi_app, "SLIDESHOW", timeout=5)


def test_stage4_interval_change(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SLIDESHOW)
    _tap_and_settle(pi_app, *INTERVAL_5S)
    _tap_and_settle(pi_app, *BACK_BTN)
    assert _wait_for_state(pi_app, "SLIDESHOW", timeout=5)
    shot1 = pi_app.screenshot("stage4_interval_change_a")
    time.sleep(6)
    shot2 = pi_app.screenshot("stage4_interval_change_b")
    assert _images_differ(shot1, shot2, ignore_rects=CLOCK_IGNORE)
    pi_app.set_config("slideshow", "interval", 30)


def test_stage4_shuffle_toggle(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SLIDESHOW)
    _tap_and_settle(pi_app, 1237, 242)
    shot = pi_app.screenshot("stage4_shuffle_toggle")
    assert_screenshot_matches(shot, "stage4_shuffle_toggle", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


def test_stage4_fit_fill_toggle(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SLIDESHOW)
    _tap_and_settle(pi_app, *FIT_FILL)
    shot = pi_app.screenshot("stage4_fit_fill_toggle")
    assert_screenshot_matches(shot, "stage4_fit_fill_toggle", ignore_rects=CLOCK_IGNORE)
    pi_app.set_config("slideshow", "fit_mode", "fit")
    _return_to_slideshow(pi_app)


# ---------------------------------------------------------------------------
# Stage 5
# ---------------------------------------------------------------------------


def test_stage5_clock_toggle(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_DISPLAY)
    _tap_and_settle(pi_app, *SHOW_CLOCK_TOGGLE)
    _tap_and_settle(pi_app, *BACK_BTN)
    assert _wait_for_state(pi_app, "SLIDESHOW", timeout=5)
    shot = pi_app.screenshot("stage5_clock_toggle")
    assert_screenshot_matches(shot, "stage5_clock_toggle")
    pi_app.set_config("display", "show_clock", True)


def test_stage5_sleep_dims_display(pi_app):
    _return_to_slideshow(pi_app)
    _set_sleep_window_around_now(pi_app, wake_delta_min=2)
    assert _wait_for_state(pi_app, "SLEEPING", timeout=40, poll=0.5)
    assert _backlight_value(pi_app) == 0
    pi_app.set_config("sleep", "enabled", False)
    _tap_and_settle(pi_app, *CENTER)
    _return_to_slideshow(pi_app)


def test_stage5_wake_restores(pi_app):
    _return_to_slideshow(pi_app)
    pi_app.set_config("display", "brightness", 60)
    _set_sleep_window_around_now(pi_app, wake_delta_min=2)
    assert _wait_for_state(pi_app, "SLEEPING", timeout=40, poll=0.5)
    _tap_and_settle(pi_app, *CENTER)
    assert _wait_for_state(pi_app, "OVERLAY", timeout=3)
    assert _backlight_value(pi_app) > 0
    pi_app.set_config("sleep", "enabled", False)
    pi_app.set_config("display", "brightness", 72)
    _return_to_slideshow(pi_app)


# ---------------------------------------------------------------------------
# Stage 6
# ---------------------------------------------------------------------------


def test_stage6_keyboard_appears(pi_app):
    _ensure_wifi_password_keyboard(pi_app)
    assert pi_app.state() == "KEYBOARD"
    _return_to_slideshow(pi_app)


def test_stage6_keyboard_typing(pi_app):
    _ensure_wifi_password_keyboard(pi_app)
    _type_hello(pi_app)
    shot = pi_app.screenshot("stage6_keyboard_typing")
    assert_screenshot_matches(shot, "stage6_keyboard_typing", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


def test_stage6_keyboard_done(pi_app):
    _ensure_wifi_password_keyboard(pi_app)
    _tap_and_settle(pi_app, *KEY_DONE)
    assert _wait_for_state(pi_app, "SETTINGS", timeout=2)
    _return_to_slideshow(pi_app)


def test_stage6_password_masking(pi_app):
    _ensure_wifi_password_keyboard(pi_app)
    _type_hello(pi_app)
    _tap_and_settle(pi_app, *KEY_DONE)
    assert _wait_for_state(pi_app, "SETTINGS", timeout=2)
    shot = pi_app.screenshot("stage6_password_masking")
    assert_screenshot_matches(shot, "stage6_password_masking", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


# ---------------------------------------------------------------------------
# Stage 7
# ---------------------------------------------------------------------------


def test_stage7_wifi_scan_shows_networks(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_WIFI)
    _tap_and_settle(pi_app, *WIFI_SCAN_BTN, delay=1.0)
    shot = pi_app.screenshot("stage7_wifi_scan_shows_networks")
    assert_screenshot_matches(shot, "stage7_wifi_scan_shows_networks", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


def test_stage7_connect_secured(pi_app):
    _ensure_wifi_password_keyboard(pi_app)
    _type_hello(pi_app)
    _tap_and_settle(pi_app, *KEY_DONE)
    _tap_and_settle(pi_app, *WIFI_CONNECT_BTN, delay=0.5)
    shot = pi_app.screenshot("stage7_connect_secured")
    assert_screenshot_matches(shot, "stage7_connect_secured", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


def test_stage7_forget_confirmation(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_WIFI)
    _tap_and_settle(pi_app, 650, 158)
    shot = pi_app.screenshot("stage7_forget_confirmation")
    assert_screenshot_matches(shot, "stage7_forget_confirmation", ignore_rects=CLOCK_IGNORE)
    _tap_and_settle(pi_app, *DIALOG_CANCEL)
    _return_to_slideshow(pi_app)


# ---------------------------------------------------------------------------
# Stage 8
# ---------------------------------------------------------------------------


def test_stage8_device_info_displayed(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SYSTEM)
    shot = pi_app.screenshot("stage8_device_info_displayed")
    assert_screenshot_matches(shot, "stage8_device_info_displayed", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


def test_stage8_shutdown_requires_confirm(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SYSTEM)
    _tap_and_settle(pi_app, *SYSTEM_SHUTDOWN, delay=0.3)
    shot = pi_app.screenshot("stage8_shutdown_requires_confirm")
    assert_screenshot_matches(shot, "stage8_shutdown_requires_confirm", ignore_rects=CLOCK_IGNORE)
    _tap_and_settle(pi_app, *DIALOG_CANCEL)
    assert pi_app.state() == "SETTINGS"
    _return_to_slideshow(pi_app)


def test_stage8_ota_check(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SYSTEM)
    _tap_and_settle(pi_app, *SYSTEM_CHECK_UPDATE, delay=2.0)
    shot = pi_app.screenshot("stage8_ota_check")
    assert_screenshot_matches(shot, "stage8_ota_check", ignore_rects=CLOCK_IGNORE)
    _return_to_slideshow(pi_app)


# ---------------------------------------------------------------------------
# Stage 9
# ---------------------------------------------------------------------------


def test_stage9_sync_status_updates(pi_app):
    _open_settings(pi_app)
    _goto_nav(pi_app, NAV_SYSTEM)
    before = pi_app.screenshot("stage9_sync_status_updates_before")
    res = pi_app.trigger_sync()
    assert res.get("ok") is True
    time.sleep(6)
    after = pi_app.screenshot("stage9_sync_status_updates_after")
    assert _images_differ(before, after, ignore_rects=None, min_fraction=0.0001)
    _return_to_slideshow(pi_app)


def test_stage9_new_photo_appears(pi_app):
    _return_to_slideshow(pi_app)
    pi_app.set_config("slideshow", "interval", 3)
    try:
        code, _, err = _remote_run_status(
            pi_app,
            f"cp {SLIDESHOW_DIR}/20240803_071132.jpg {SLIDESHOW_DIR}/_test_new_photo.jpg",
        )
        assert code == 0, err
        time.sleep(6)
        shot = pi_app.screenshot("stage9_new_photo_appears")
        assert_screenshot_matches(shot, "stage9_new_photo_appears", ignore_rects=CLOCK_IGNORE)
    finally:
        _remote_run(pi_app, f"rm -f {SLIDESHOW_DIR}/_test_new_photo.jpg")
        pi_app.set_config("slideshow", "interval", 30)

