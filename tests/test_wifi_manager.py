import os
from unittest.mock import patch

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from piframe.wifi_manager import WifiManager


def make_scan_output():
    return (
        "HomeNetwork:WPA2:85\n"
        "GuestWifi:WPA2:60\n"
        "OpenCafe::45\n"
        "WeakSignal:WPA2:20\n"
    )


def run_async_inline(manager: WifiManager, method_name: str, *args):
    captured = []

    class ImmediateThread:
        def __init__(self, *a, target=None, daemon=None, **kw):
            _ = a, daemon, kw
            captured.append(target)

        def start(self):
            captured[0]()

    with patch("piframe.wifi_manager.threading.Thread", ImmediateThread):
        getattr(manager, method_name)(*args)


def test_scan_parses_networks():
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(True, make_scan_output())):
        with patch.object(manager, "_post") as mock_post:
            run_async_inline(manager, "scan")
            result = mock_post.call_args[0][0]
            assert result.operation == "scan"
            assert result.success is True
            networks = result.data
            assert len(networks) == 4
            assert networks[0].ssid == "HomeNetwork"
            assert networks[0].signal == 85
            assert networks[2].ssid == "OpenCafe"
            assert networks[2].security == ""


def test_connect_with_password_builds_correct_command():
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(True, "")) as run_mock:
        with patch.object(manager, "_post"):
            run_async_inline(manager, "connect", "MySSID", "mypassword")
            cmd = run_mock.call_args[0][0]
            assert "nmcli" in cmd
            assert "MySSID" in cmd
            assert "mypassword" in cmd


def test_connect_without_password():
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(True, "")) as run_mock:
        with patch.object(manager, "_post"):
            run_async_inline(manager, "connect", "OpenNet", None)
            cmd = run_mock.call_args[0][0]
            assert "password" not in cmd
            assert "OpenNet" in cmd


def test_forget_builds_correct_command():
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(True, "")) as run_mock:
        with patch.object(manager, "_post"):
            run_async_inline(manager, "forget", "HomeNetwork")
            cmd = run_mock.call_args[0][0]
            assert "delete" in cmd
            assert "HomeNetwork" in cmd


def test_get_status_parses_connected():
    connected_output = "GENERAL.CONNECTION:HomeNetwork\nIP4.ADDRESS[1]:192.168.1.100/24\n"
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(True, connected_output)):
        with patch.object(manager, "_post") as mock_post:
            run_async_inline(manager, "get_status")
            result = mock_post.call_args[0][0]
            assert result.operation == "status"
            assert result.success is True
            status = result.data
            assert status.connected is True
            assert status.ssid == "HomeNetwork"
            assert "192.168.1.100" in status.ip_address


def test_get_status_parses_disconnected():
    disconnected_output = "GENERAL.CONNECTION:--\nIP4.ADDRESS[1]:\n"
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(True, disconnected_output)):
        with patch.object(manager, "_post") as mock_post:
            run_async_inline(manager, "get_status")
            result = mock_post.call_args[0][0]
            status = result.data
            assert status.connected is False
            assert status.ssid == ""


def test_get_status_timeout():
    manager = WifiManager()
    with patch.object(manager, "_run_cmd", return_value=(False, "timeout")):
        with patch.object(manager, "_post") as mock_post:
            run_async_inline(manager, "get_status")
            result = mock_post.call_args[0][0]
            assert result.success is False
