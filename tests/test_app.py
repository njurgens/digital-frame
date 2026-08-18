"""Tests for the App entry point: PID-file lifecycle, headless boot, and IPC."""

from __future__ import annotations

import json
import os
import socket
import stat
import sys
import time
from pathlib import Path

import pytest

import piframe.app as app_module
from piframe.app import App, acquire_pid_file

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pid_file(tmp_path: Path) -> Path:
    """Return a per-test path for the slideshow PID file."""
    return tmp_path / "slideshow.pid"


def test_acquire_pid_file_writes_pid_and_holds_lock(pid_file: Path) -> None:
    """Acquiring the PID file writes the PID, holds an exclusive lock, and is 0600."""
    fd = acquire_pid_file(pid_file)
    try:
        assert pid_file.read_text().strip() == str(os.getpid())
        assert stat.S_IMODE(pid_file.stat().st_mode) == 0o600
        with pytest.raises(SystemExit):
            acquire_pid_file(pid_file)
    finally:
        os.close(fd)
    # Closing the fd releases the lock: acquisition succeeds again.
    fd = acquire_pid_file(pid_file)
    os.close(fd)


def _boot_app(
    pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ipc_enabled: bool = False
) -> App:
    """Boot the real app headless with a local-provider config in *tmp_path*.

    The runtime dir is pointed at *tmp_path* so the PID file (and the IPC
    socket, when enabled) land in the per-test directory.
    """
    config = tmp_path / "config.toml"
    ipc_section = "[ipc]\nenabled = true\n\n" if ipc_enabled else ""
    config.write_text(
        "[app]\n"
        "mock_wifi = true\n"
        "\n"
        f"{ipc_section}"
        "[sync]\n"
        'provider = "local"\n'
        f'source_dir = "{REPO_ROOT / "tests" / "fixtures" / "stock"}"\n'
    )
    monkeypatch.setattr(app_module, "resolve_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(app_module, "CONFIG_PATH", config)
    monkeypatch.setattr(sys, "argv", ["slideshow", "--windowed"])
    return App()


def test_app_boots_headless_with_local_provider(
    pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app boots with the dummy video driver and a local-provider config."""
    app = _boot_app(pid_file, tmp_path, monkeypatch)
    try:
        assert pid_file.read_text().strip() == str(os.getpid())
        assert app._screen.get_size() == (1280, 800)
    finally:
        os.close(app._pid_fd)


def test_app_ipc_roundtrip_state(
    pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With [ipc] enabled, a state request over the socket gets a JSON-RPC response."""
    app = _boot_app(pid_file, tmp_path, monkeypatch, ipc_enabled=True)
    try:
        sock_path = tmp_path / "piframe.sock"
        assert sock_path.exists()
        assert stat.S_IMODE(sock_path.stat().st_mode) == 0o600
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.connect(str(sock_path))
        client.sendall(b'{"jsonrpc": "2.0", "method": "state", "id": 1}\n')
        client.setblocking(False)
        data = b""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            app._drain_ipc_queue()
            try:
                chunk = client.recv(4096)
            except BlockingIOError:
                chunk = b""
            if chunk:
                data += chunk
                if data.endswith(b"\n"):
                    break
            time.sleep(0.01)
        client.close()
        assert json.loads(data) == {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 1}
    finally:
        os.close(app._pid_fd)
