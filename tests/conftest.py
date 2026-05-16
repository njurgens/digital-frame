"""Shared pytest fixtures for all test tiers."""
import os
import socket
import time
import json
import queue
import threading
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

    def __init__(self, ssh, local_port: int):
        self._ssh = ssh
        self._port = local_port

    def _send(self, obj: dict) -> dict:
        with socket.create_connection(("127.0.0.1", self._port), timeout=10) as s:
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
    """Start the app on the Pi in harness mode and yield an AppHarness."""
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

    # Kill any running instance first
    ssh.exec_command("kill -9 $(cat /tmp/slideshow.pid 2>/dev/null) 2>/dev/null; sleep 0.5")
    time.sleep(1)

    # Ensure socat bridge is running (TCP 9901 → Unix socket)
    ssh.exec_command(
        f"pkill -f 'socat TCP-LISTEN:{BRIDGE_PORT}' 2>/dev/null; sleep 0.2; "
        f"nohup socat TCP-LISTEN:{BRIDGE_PORT},reuseaddr,fork "
        f"UNIX-CLIENT:{SOCK_PATH} >/dev/null 2>&1 &"
    )

    # Launch the app in harness mode
    ssh.exec_command(
        f"XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-0 "
        f"python3 {APP_DIR}/slideshow.py --test-harness --mock-wifi "
        f"> /tmp/slideshow.log 2>&1 &"
    )
    time.sleep(4)  # wait for startup

    # Forward local BRIDGE_PORT to Pi BRIDGE_PORT via SSH tunnel
    transport = ssh.get_transport()
    transport.request_port_forward("", BRIDGE_PORT)

    class _ForwardThread(threading.Thread):
        daemon = True

        def run(self):
            while True:
                try:
                    chan = transport.accept(timeout=1)
                    if chan is None:
                        continue
                    threading.Thread(
                        target=_forward_channel,
                        args=(chan,),
                        daemon=True,
                    ).start()
                except Exception:
                    break

    def _forward_channel(chan):
        with socket.create_connection(("127.0.0.1", BRIDGE_PORT)) as sock:
            stop = threading.Event()

            def fwd(src, dst):
                try:
                    while not stop.is_set():
                        data = src.recv(4096)
                        if not data:
                            break
                        dst.sendall(data)
                finally:
                    stop.set()

            t1 = threading.Thread(target=fwd, args=(chan, sock), daemon=True)
            t2 = threading.Thread(target=fwd, args=(sock, chan), daemon=True)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

    _ForwardThread().start()

    harness = AppHarness(ssh, BRIDGE_PORT)
    yield harness

    harness.quit()
    ssh.exec_command(f"pkill -f 'socat TCP-LISTEN:{BRIDGE_PORT}' 2>/dev/null")
    ssh.close()
