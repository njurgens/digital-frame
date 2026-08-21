"""Tests for the IPC client: one JSON-RPC request per connection, plus the CLI."""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable, Generator
from pathlib import Path

import pytest

from piframe import ipc_client, runtime_paths
from piframe.ipc_client import IpcClient, IpcRpcError, IpcTransportError


class FakeIpcServer:
    """A stand-in for the app's IPC server: one scripted reply per connection.

    The handler receives the parsed request and returns the response line to
    send (bytes) or None for no response (a notification).  *delay* sleeps
    before the reply, to simulate a stalled server.
    """

    def __init__(
        self,
        path: Path,
        handler: Callable[[dict], bytes | None] | None = None,
        delay: float = 0.0,
    ) -> None:
        """Bind *path* and start the accept thread."""
        self._path = path
        self._handler = handler or (
            lambda req: json.dumps({"jsonrpc": "2.0", "result": {}, "id": req.get("id")}).encode()
        )
        self._delay = delay
        self.requests: list[dict] = []
        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(path))
        self._server.listen(5)
        # A short accept timeout keeps stop() fast: on Linux, close() does
        # not wake a thread blocked in accept().
        self._server.settimeout(0.25)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            try:
                conn, _ = self._server.accept()
            except TimeoutError:
                continue  # no connection yet: re-check (stop() closes the listener)
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn: socket.socket) -> None:
        try:
            data = b""
            while b"\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                data += chunk
            request = json.loads(data)
            self.requests.append(request)
            if self._delay:
                import time

                time.sleep(self._delay)
            line = self._handler(request)
            if line is not None:
                conn.sendall(line)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self) -> None:
        """Close the listener and wait for the accept thread."""
        self._server.close()
        self._thread.join(timeout=1)


@pytest.fixture
def server(tmp_path: Path) -> Generator[FakeIpcServer]:
    """A fake server listening on the fixture's socket path."""
    srv = FakeIpcServer(tmp_path / "piframe.sock")
    yield srv
    srv.stop()


def make_client(tmp_path: Path) -> IpcClient:
    """A client pointed at the fixture's socket."""
    return IpcClient(socket_path=tmp_path / "piframe.sock")


def _result_line(result: object) -> bytes:
    """A success response line carrying *result*."""
    return (json.dumps({"jsonrpc": "2.0", "result": result, "id": 1}) + "\n").encode()


def _error_line(code: int, message: str) -> bytes:
    return (
        json.dumps({"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": 1}) + "\n"
    ).encode()


# --- core call() -------------------------------------------------------------


def test_call_success_returns_result(server: FakeIpcServer, tmp_path: Path) -> None:
    """A success response returns its result and the request is well-formed."""
    server._handler = lambda req: _result_line({"state": "SLIDESHOW"})
    assert make_client(tmp_path).call("state") == {"state": "SLIDESHOW"}
    assert server.requests == [{"jsonrpc": "2.0", "method": "state", "id": 1}]


def test_call_error_response_raises_rpc_error(server: FakeIpcServer, tmp_path: Path) -> None:
    """An error response raises IpcRpcError carrying the code and message."""
    server._handler = lambda req: _error_line(-32601, "method not found: nope")
    with pytest.raises(IpcRpcError) as exc:
        make_client(tmp_path).call("nope")
    assert exc.value.code == -32601
    assert "nope" in exc.value.message


def test_call_notification_sends_no_id_and_returns_none(
    server: FakeIpcServer, tmp_path: Path
) -> None:
    """A notification carries no id and gets no response."""
    server._handler = lambda req: None
    assert make_client(tmp_path).call("quit", notification=True) is None
    # The client returns before the server records the request: wait for it.
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not server.requests:
        time.sleep(0.01)
    assert server.requests == [{"jsonrpc": "2.0", "method": "quit"}]


def test_call_connect_failure_raises_transport_error(tmp_path: Path) -> None:
    """Connecting to a missing socket raises IpcTransportError."""
    with pytest.raises(IpcTransportError):
        make_client(tmp_path).call("state")


def test_call_read_timeout_raises_transport_error(tmp_path: Path) -> None:
    """A server that stalls past the read timeout raises IpcTransportError."""
    srv = FakeIpcServer(tmp_path / "piframe.sock", delay=1.0)
    try:
        with pytest.raises(IpcTransportError, match="timed out"):
            IpcClient(socket_path=tmp_path / "piframe.sock", timeout=0.2).call("state")
    finally:
        srv.stop()


def test_call_garbage_response_raises_transport_error(
    server: FakeIpcServer, tmp_path: Path
) -> None:
    """A response line that is not JSON raises IpcTransportError."""
    server._handler = lambda req: b"not json\n"
    with pytest.raises(IpcTransportError):
        make_client(tmp_path).call("state")


def test_call_response_without_result_or_error(server: FakeIpcServer, tmp_path: Path) -> None:
    """A response object with neither result nor error raises IpcTransportError."""
    server._handler = lambda req: b'{"jsonrpc": "2.0"}\n'
    with pytest.raises(IpcTransportError):
        make_client(tmp_path).call("state")


def test_call_malformed_error_object_raises_transport_error(
    server: FakeIpcServer, tmp_path: Path
) -> None:
    """An error member that is not a well-formed object is a transport failure."""
    server._handler = lambda req: b'{"jsonrpc": "2.0", "error": null, "id": 1}\n'
    with pytest.raises(IpcTransportError):
        make_client(tmp_path).call("state")


# --- typed methods -----------------------------------------------------------


def test_state_returns_dict(server: FakeIpcServer, tmp_path: Path) -> None:
    """state() returns the server's result dict."""
    server._handler = lambda req: _result_line({"state": "SLIDESHOW"})
    assert make_client(tmp_path).state() == {"state": "SLIDESHOW"}


def test_play_pause_returns_dict(server: FakeIpcServer, tmp_path: Path) -> None:
    """play_pause() returns the paused state."""
    server._handler = lambda req: _result_line({"paused": True})
    assert make_client(tmp_path).play_pause() == {"paused": True}


def test_tap_sends_params(server: FakeIpcServer, tmp_path: Path) -> None:
    """Tap sends its coordinates as named params."""
    make_client(tmp_path).tap(100, 200)
    assert server.requests[0]["params"] == {"x": 100, "y": 200}


def test_swipe_sends_params_with_default_ms(server: FakeIpcServer, tmp_path: Path) -> None:
    """Swipe defaults ms to 300."""
    make_client(tmp_path).swipe(1, 2, 3, 4)
    assert server.requests[0]["params"] == {"x": 1, "y": 2, "dx": 3, "dy": 4, "ms": 300}


def test_swipe_sends_explicit_ms(server: FakeIpcServer, tmp_path: Path) -> None:
    """Swipe sends an explicit ms."""
    make_client(tmp_path).swipe(1, 2, 3, 4, ms=1500)
    assert server.requests[0]["params"]["ms"] == 1500


def test_screenshot_sends_path(server: FakeIpcServer, tmp_path: Path) -> None:
    """Screenshot sends its path as a named param."""
    make_client(tmp_path).screenshot("/tmp/view.png")
    assert server.requests[0]["params"] == {"path": "/tmp/view.png"}


def test_set_config_sends_value(server: FakeIpcServer, tmp_path: Path) -> None:
    """set_config sends section, key, and the value."""
    make_client(tmp_path).set_config("display", "interval", 17)
    assert server.requests[0]["params"] == {"section": "display", "key": "interval", "value": 17}


def test_prev_next_trigger_sync_send_no_params(server: FakeIpcServer, tmp_path: Path) -> None:
    """prev, next, and trigger_sync send no params member."""
    client = make_client(tmp_path)
    client.prev()
    client.next()
    client.trigger_sync()
    assert all("params" not in req for req in server.requests)


def test_quit_is_a_notification(server: FakeIpcServer, tmp_path: Path) -> None:
    """Quit is a notification: the request carries no id."""
    make_client(tmp_path).quit()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and not server.requests:
        time.sleep(0.01)
    assert "id" not in server.requests[0]


# --- socket resolution -------------------------------------------------------


def _make_runtime_dir(d: Path) -> None:
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o700)


def test_resolve_prefers_xdg_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With XDG_RUNTIME_DIR set and a socket in both dirs, the XDG one wins."""
    xdg = tmp_path / "xdg"
    _make_runtime_dir(xdg)
    home = tmp_path / "home"
    (home / ".local" / "piframe").mkdir(parents=True)
    (home / ".local" / "piframe" / "piframe.sock").touch()
    (xdg / "piframe.sock").touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
    monkeypatch.setenv("HOME", str(home))
    assert ipc_client.resolve_socket_path() == xdg / "piframe.sock"


def test_resolve_uses_fallback_when_xdg_socket_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With XDG set but its socket missing, the fallback's socket is found."""
    xdg = tmp_path / "xdg"
    _make_runtime_dir(xdg)
    home = tmp_path / "home"
    (home / ".local" / "piframe").mkdir(parents=True)
    (home / ".local" / "piframe" / "piframe.sock").touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg))
    monkeypatch.setenv("HOME", str(home))
    assert ipc_client.resolve_socket_path() == home / ".local" / "piframe" / "piframe.sock"


def test_resolve_uses_fallback_when_xdg_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without XDG_RUNTIME_DIR, the fallback dir's socket is used."""
    home = tmp_path / "home"
    (home / ".local" / "piframe").mkdir(parents=True)
    (home / ".local" / "piframe" / "piframe.sock").touch()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert ipc_client.resolve_socket_path() == home / ".local" / "piframe" / "piframe.sock"


def test_resolve_returns_resolved_dir_path_when_no_socket_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no socket in either location, the resolved dir's path is returned."""
    # Sandbox the second candidate: without this the test probes the real
    # /run/user/{uid} (not hermetic if the app runs in the same session).
    monkeypatch.setattr(runtime_paths, "system_runtime_dir", lambda: tmp_path / "system")
    home = tmp_path / "home"
    (home / ".local" / "piframe").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert ipc_client.resolve_socket_path() == home / ".local" / "piframe" / "piframe.sock"


def test_explicit_socket_path_bypasses_resolution(tmp_path: Path) -> None:
    """An explicit --socket path is used as-is, even if it does not exist."""
    custom = tmp_path / "custom.sock"
    client = IpcClient(socket_path=custom)
    assert client.socket_path == custom


# --- CLI ---------------------------------------------------------------------


def _cli(tmp_path: Path, *args: str) -> int:
    return ipc_client.main(["--socket", str(tmp_path / "piframe.sock"), *args])


def test_cli_state_prints_result_json(
    server: FakeIpcServer, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A successful command exits 0 and prints the result as JSON."""
    server._handler = lambda req: _result_line({"state": "SLIDESHOW"})
    assert _cli(tmp_path, "state") == 0
    assert json.loads(capsys.readouterr().out) == {"state": "SLIDESHOW"}


def test_cli_quit_prints_nothing(
    server: FakeIpcServer, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Quit is a notification: exit 0 and no output."""
    server._handler = lambda req: None
    assert _cli(tmp_path, "quit") == 0
    assert capsys.readouterr().out == ""


def test_cli_screenshot(
    server: FakeIpcServer, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Screenshot --path passes the path through to the server."""
    server._handler = lambda req: _result_line({})
    assert _cli(tmp_path, "screenshot", "--path", "/tmp/view.png") == 0
    assert server.requests[0]["params"] == {"path": "/tmp/view.png"}


def test_cli_swipe_with_ms(
    server: FakeIpcServer, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Swipe --ms passes the duration through to the server."""
    server._handler = lambda req: _result_line({})
    assert _cli(tmp_path, "swipe", "1", "2", "3", "4", "--ms", "1500") == 0
    assert server.requests[0]["params"]["ms"] == 1500


def test_cli_set_config_parses_json_scalars(
    server: FakeIpcServer, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The set_config value is parsed as a JSON scalar (number, bool, string)."""
    server._handler = lambda req: _result_line({})
    assert _cli(tmp_path, "set_config", "display", "interval", "17") == 0
    assert server.requests[0]["params"]["value"] == 17
    assert _cli(tmp_path, "set_config", "display", "brightness", "true") == 0
    assert server.requests[1]["params"]["value"] is True
    assert _cli(tmp_path, "set_config", "display", "mode", '"night"') == 0
    assert server.requests[2]["params"]["value"] == "night"


def test_cli_set_config_rejects_non_scalar(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """A value that is not a JSON scalar is a usage error (exit 2)."""
    assert _cli(tmp_path, "set_config", "a", "b", "not-json") == 2
    assert _cli(tmp_path, "set_config", "a", "b", "null") == 2
    assert _cli(tmp_path, "set_config", "a", "b", "[1]") == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_cli_unknown_command_is_usage_error(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """An unknown subcommand is a usage error (exit 2)."""
    assert _cli(tmp_path, "frobnicate") == 2


def test_cli_missing_argument_is_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A missing positional argument is a usage error (exit 2)."""
    assert _cli(tmp_path, "tap") == 2


def test_cli_transport_error_exits_1(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """No server at the socket: exit 1 and an error naming the socket."""
    assert _cli(tmp_path, "state") == 1
    err = capsys.readouterr().err
    assert "error:" in err
    assert str(tmp_path / "piframe.sock") in err


def test_cli_protocol_error_exits_3(
    server: FakeIpcServer, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """A server error response: exit 3 and the error message on stderr."""
    server._handler = lambda req: _error_line(-32602, "missing param: x")
    assert _cli(tmp_path, "swipe", "1", "2", "3", "4") == 3
    err = capsys.readouterr().err
    assert "error:" in err
    assert "missing param: x" in err
