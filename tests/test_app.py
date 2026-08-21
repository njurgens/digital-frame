"""Tests for the App entry point: PID-file lifecycle, headless boot, and IPC."""

from __future__ import annotations

import fcntl
import json
import logging
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
    monkeypatch.setattr(app_module, "fallback_dir", lambda: tmp_path / "fallback")
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
        # [ipc] disabled: no socket is created (the default-off safety property).
        assert not (tmp_path / "piframe.sock").exists()
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
        if app._ipc is not None:
            app._ipc.stop()
        os.close(app._pid_fd)


def test_app_rejects_removed_test_harness_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The retired --test-harness flag is an argument error (V-1)."""
    monkeypatch.setattr(app_module, "resolve_runtime_dir", lambda: tmp_path)
    monkeypatch.setattr(app_module, "fallback_dir", lambda: tmp_path / "fallback")
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(sys, "argv", ["slideshow", "--test-harness"])
    with pytest.raises(SystemExit):
        App()


def test_app_fails_closed_when_fallback_dir_uncreatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-2: an uncreatable fallback dir (unwritable ~/.local) fails closed.

    The error names the directory.
    """
    home = tmp_path / "home"
    (home / ".local").mkdir(parents=True)
    (home / ".local").chmod(0o555)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(app_module, "fallback_dir", lambda: home / ".local" / "piframe")
    monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_path / "config.toml")
    monkeypatch.setattr(sys, "argv", ["slideshow", "--windowed"])
    with pytest.raises(OSError, match="cannot create fallback runtime dir"):
        App()


def test_app_refuses_when_other_location_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second instance is refused when the other location is locked.

    The lock is per-resolved-dir, so a second launch that resolves a
    different candidate location is refused by the cross-location probe.
    """
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_pid = other_dir / "slideshow.pid"
    other_pid.write_text("12345\n")
    fd = os.open(other_pid, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)  # hold the lock in the test process
    try:
        monkeypatch.setattr(app_module, "resolve_runtime_dir", lambda: tmp_path)
        monkeypatch.setattr(app_module, "fallback_dir", lambda: other_dir)
        monkeypatch.setattr(app_module, "CONFIG_PATH", tmp_path / "config.toml")
        monkeypatch.setattr(sys, "argv", ["slideshow", "--windowed"])
        with pytest.raises(SystemExit):
            App()
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_app_continues_without_api_when_ipc_server_fails(
    pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-3: a failing IPC server does not stop the app (fail-soft).

    With the API enabled but the server failing to start, the app boots
    without the API and no socket is present.
    """

    class _FailingIpcModule:
        def create(self, config: object, **deps: object) -> object:
            raise OSError("simulated bind failure")
            raise OSError("simulated bind failure")

    monkeypatch.setattr(app_module, "IpcModule", _FailingIpcModule)
    app = _boot_app(pid_file, tmp_path, monkeypatch, ipc_enabled=True)
    try:
        assert app._ipc is None
        assert not (tmp_path / "piframe.sock").exists()
    finally:
        os.close(app._pid_fd)


def test_ipc_executor_keys_match_method_names(
    pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dispatch table covers exactly the documented method names (D-5)."""
    app = _boot_app(pid_file, tmp_path, monkeypatch)
    try:
        assert set(app._ipc_executors) == app_module.IPC_METHOD_NAMES
    finally:
        os.close(app._pid_fd)


def test_app_logs_ipc_disabled_when_config_off(
    pid_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With the API disabled by config, the startup log says so (D-6)."""
    with caplog.at_level(logging.INFO):
        app = _boot_app(pid_file, tmp_path, monkeypatch)
    try:
        assert any("IPC: disabled by config" in m for m in caplog.messages)
    finally:
        os.close(app._pid_fd)


def test_app_logs_ipc_listening_when_bound(
    pid_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With the API enabled and bound, the startup log names the socket path (D-6)."""
    with caplog.at_level(logging.INFO):
        app = _boot_app(pid_file, tmp_path, monkeypatch, ipc_enabled=True)
    try:
        expected = f"IPC: listening on {tmp_path / 'piframe.sock'}"
        assert any(expected in m for m in caplog.messages)
    finally:
        os.close(app._pid_fd)


def test_app_logs_ipc_unavailable_when_server_fails(
    pid_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """With the API enabled but the server failing, the startup log says unavailable (D-6)."""

    class _FailingIpcModule:
        def create(self, config: object, **deps: object) -> object:
            raise OSError("simulated bind failure")

    monkeypatch.setattr(app_module, "IpcModule", _FailingIpcModule)
    with caplog.at_level(logging.INFO):
        app = _boot_app(pid_file, tmp_path, monkeypatch, ipc_enabled=True)
    try:
        assert app._ipc is None
        assert any("IPC: enabled but unavailable" in m for m in caplog.messages)
    finally:
        os.close(app._pid_fd)
