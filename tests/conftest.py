"""Shared pytest fixtures for all test tiers."""
import os
import socket
import time
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

# Must be set before any pygame import
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

# ---------------------------------------------------------------------------
# Tier 1 / 2 — local fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def pygame_init():
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


@pytest.fixture
def mock_backlight():
    with patch("piframe.backlight.open", MagicMock()) as m:
        yield m


@pytest.fixture
def mock_nmcli():
    """Returns a mock that replaces subprocess.run inside WifiManager."""
    with patch("piframe.wifi_manager.subprocess.run") as m:
        yield m


# ---------------------------------------------------------------------------
# Tier 3 — integration fixtures (require Pi SSH access)
# ---------------------------------------------------------------------------

DEVICE_HOST = "10.1.7.58"
DEVICE_USER = "frame"
DEVICE_KEY  = Path.home() / ".ssh" / "id_ed25519"
APP_DIR     = "/home/frame/digital-frame"
SOCK_PATH   = "/tmp/piframe_test.sock"
GOLDEN_DIR  = Path(__file__).parent / "golden"
BRIDGE_PORT = 9901  # local TCP port forwarded to SOCK_PATH via socat


class AppHarness:
    """Thin wrapper around the test-harness socket protocol."""

    def __init__(self, ssh, host: str, port: int, sock_path: str | None = None):
        self._ssh = ssh
        self._host = host
        self._port = port
        self._sock_path = sock_path  # if set, connect via Unix socket directly

    def _connect(self):
        """Return a connected socket (Unix or TCP)."""
        if self._sock_path:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect(self._sock_path)
        else:
            s = socket.create_connection((self._host, self._port), timeout=10)
        return s

    def _send(self, obj: dict) -> dict:
        with self._connect() as s:
            s.sendall((json.dumps(obj) + "\n").encode())
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
        return json.loads(data.strip())

    def cmd(self, obj: dict) -> dict:
        return self._send(obj)

    def tap(self, x: int, y: int) -> dict:
        return self.cmd({"cmd": "tap", "x": x, "y": y})

    def swipe(self, x: int, y: int, dx: int, dy: int, ms: int = 300) -> dict:
        return self.cmd({"cmd": "swipe", "x": x, "y": y, "dx": dx, "dy": dy, "ms": ms})

    def state(self) -> str:
        return self.cmd({"cmd": "state"})["state"]

    def set_config(self, section: str, key: str, value) -> dict:
        return self.cmd({"cmd": "set_config", "section": section, "key": key, "value": value})

    def trigger_sync(self) -> dict:
        return self.cmd({"cmd": "trigger_sync"})

    def screenshot(self, name: str) -> Path:
        remote = f"/tmp/pf_{name}.png"
        self.cmd({"cmd": "screenshot", "path": remote})
        time.sleep(0.3)
        local = Path(f"/tmp/pf_{name}.png")
        if self._sock_path:
            # Running on-device: screenshot is already saved locally.
            return local
        sftp = self._ssh.open_sftp()
        sftp.get(remote, str(local))
        sftp.close()
        return local

    def quit(self) -> None:
        try:
            self.cmd({"cmd": "quit"})
        except Exception:
            pass


@pytest.fixture(scope="module")
def pi_app():
    """Connect to (or start) the app on the Pi in harness mode and yield an AppHarness."""
    try:
        import paramiko
    except ImportError:
        pytest.skip("paramiko not installed — integration tests require it")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        DEVICE_HOST,
        username=DEVICE_USER,
        key_filename=str(DEVICE_KEY),
        timeout=10,
    )

    # When running on-device the Unix socket is directly accessible.
    # When running from a remote machine, fall back to socat TCP bridge.
    _on_device = (DEVICE_HOST in ("127.0.0.1", "localhost") or _is_on_device())

    def _app_is_ready() -> bool:
        """Return True if the app's Unix socket is up and answering."""
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(SOCK_PATH)
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
            return b"state" in data
        except Exception:
            return False

    # Ensure app is running in harness mode.
    if not _app_is_ready():
        # Try to start it.
        ssh.exec_command(
            f"XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 "
            f"nohup python3 {APP_DIR}/slideshow.py --test-harness --mock-wifi "
            f"</dev/null >>/tmp/slideshow.log 2>&1 &"
        )
        for _ in range(10):
            time.sleep(1)
            if _app_is_ready():
                break
        else:
            ssh.close()
            pytest.fail("App did not start in harness mode within 10 s")

    if _on_device:
        harness = AppHarness(ssh, DEVICE_HOST, BRIDGE_PORT, sock_path=SOCK_PATH)
    else:
        # Ensure socat bridge is up
        ssh.exec_command(
            f"pgrep socat >/dev/null 2>&1 || "
            f"nohup socat TCP-LISTEN:{BRIDGE_PORT},reuseaddr,fork "
            f"UNIX-CLIENT:{SOCK_PATH} </dev/null >/dev/null 2>&1 &"
        )
        time.sleep(1)
        harness = AppHarness(ssh, DEVICE_HOST, BRIDGE_PORT)

    yield harness

    ssh.close()


def _is_on_device() -> bool:
    """Return True if this process is running directly on the Pi."""
    try:
        import subprocess
        out = subprocess.check_output(["hostname", "-I"], text=True)
        return DEVICE_HOST in out.split()
    except Exception:
        return False
