"""Tests for the ipc module: the JSON-RPC 2.0 protocol layer and socket server."""

from __future__ import annotations

import json
import socket
import stat
import time
from pathlib import Path

import pytest

from piframe.ipc import IpcError, IpcServer, dispatch

# --- protocol layer ----------------------------------------------------------


def _state_executor(params: dict) -> dict:
    """A stand-in executor: returns the app state, ignores params."""
    return {"state": "SLIDESHOW"}


def test_dispatch_valid_request_returns_result() -> None:
    """A valid request gets a result response echoing its id."""
    resp = dispatch({"jsonrpc": "2.0", "method": "state", "id": 7}, {"state": _state_executor})
    assert resp == {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 7}


@pytest.mark.parametrize("rid", [1, "abc", 1.5, None])
def test_dispatch_echoes_each_valid_id_shape(rid: object) -> None:
    """Each valid id shape (number, string, float, null) is echoed in the response."""
    resp = dispatch({"jsonrpc": "2.0", "method": "state", "id": rid}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["id"] == rid


def test_dispatch_unknown_method_gets_method_not_found() -> None:
    """An unknown method gets -32601 with the id echoed."""
    resp = dispatch({"jsonrpc": "2.0", "method": "nope", "id": "a"}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32601
    assert "nope" in resp["error"]["message"]
    assert resp["id"] == "a"


def test_dispatch_executor_invalid_params_gets_32602() -> None:
    """An executor-raised invalid-params error gets -32602 with its message."""

    def bad(params: dict) -> dict:
        raise IpcError(-32602, "missing param: x")

    resp = dispatch({"jsonrpc": "2.0", "method": "bad", "id": 1}, {"bad": bad})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"] == {"code": -32602, "message": "missing param: x"}
    assert resp["id"] == 1


def test_dispatch_executor_exception_gets_internal_error() -> None:
    """An unexpected executor exception gets -32603 with its message."""

    def boom(params: dict) -> dict:
        raise ValueError("kaboom")

    resp = dispatch({"jsonrpc": "2.0", "method": "boom", "id": 2}, {"boom": boom})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"] == {"code": -32603, "message": "kaboom"}
    assert resp["id"] == 2


def test_dispatch_notification_produces_no_response() -> None:
    """A request without an id is a notification: executed, but no response."""
    calls: list[int] = []

    def run(params: dict) -> dict:
        calls.append(1)
        return {}

    resp = dispatch({"jsonrpc": "2.0", "method": "run"}, {"run": run})
    assert resp is None
    assert calls == [1]


def test_dispatch_failed_notification_gets_no_response() -> None:
    """A notification that fails dispatch gets no response.

    The spec says the server MUST NOT reply to a notification, even a
    failed one (here: an unknown method).
    """
    resp = dispatch({"jsonrpc": "2.0", "method": "nope"}, {"state": _state_executor})
    assert resp is None


def test_dispatch_malformed_notification_gets_no_response() -> None:
    """A notification with a malformed envelope gets no response.

    The envelope failure does not turn a notification into a request.
    """
    resp = dispatch({"method": "state"}, {"state": _state_executor})
    assert resp is None


def test_dispatch_null_id_is_a_request_not_a_notification() -> None:
    """An explicit null id is a request (the id member is present): it gets a response."""
    resp = dispatch({"jsonrpc": "2.0", "method": "state", "id": None}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["id"] is None
    assert resp["result"] == {"state": "SLIDESHOW"}


def test_dispatch_missing_jsonrpc_gets_invalid_request() -> None:
    """A request without the jsonrpc member gets -32600; the valid id is still echoed."""
    resp = dispatch({"method": "state", "id": 1}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600
    assert resp["id"] == 1


def test_dispatch_wrong_jsonrpc_version_gets_invalid_request() -> None:
    """A jsonrpc value other than "2.0" gets -32600."""
    resp = dispatch({"jsonrpc": "1.0", "method": "state", "id": 1}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600
    assert resp["id"] == 1


def test_dispatch_missing_method_gets_invalid_request() -> None:
    """A request without a method member gets -32600."""
    resp = dispatch({"jsonrpc": "2.0", "id": 1}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600


def test_dispatch_non_string_method_gets_invalid_request() -> None:
    """A non-string method gets -32600."""
    resp = dispatch({"jsonrpc": "2.0", "method": 5, "id": 1}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600


def test_dispatch_wrong_params_type_gets_invalid_request() -> None:
    """A params member that is neither an array nor an object gets -32600."""
    resp = dispatch(
        {"jsonrpc": "2.0", "method": "state", "params": "x", "id": 1}, {"state": _state_executor}
    )
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600


def test_dispatch_array_params_gets_invalid_params() -> None:
    """This API's methods take named (object) params: an array gets -32602."""
    resp = dispatch(
        {"jsonrpc": "2.0", "method": "state", "params": [1, 2], "id": 1},
        {"state": _state_executor},
    )
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32602
    assert resp["id"] == 1


def test_dispatch_bad_id_type_gets_invalid_request() -> None:
    """An id that is not a string, number, or null gets -32600 with a null response id."""
    resp = dispatch(
        {"jsonrpc": "2.0", "method": "state", "id": {"nested": True}}, {"state": _state_executor}
    )
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600
    assert resp["id"] is None


def test_dispatch_boolean_id_gets_invalid_request() -> None:
    """A boolean id is not a valid JSON-RPC id (it is not a number): -32600."""
    resp = dispatch({"jsonrpc": "2.0", "method": "state", "id": True}, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, dict)
    assert resp["error"]["code"] == -32600
    assert resp["id"] is None


def test_dispatch_non_object_gets_invalid_request() -> None:
    """A line that is valid JSON but not an object (or batch) gets -32600."""
    for value in ["just a string", 42, True]:
        resp = dispatch(value, {"state": _state_executor})
        assert resp is not None
        assert isinstance(resp, dict)
        assert resp["error"]["code"] == -32600
        assert resp["id"] is None


def test_dispatch_batch_returns_array_of_responses() -> None:
    """A batch gets an array response, one entry per request, in order."""
    batch = [
        {"jsonrpc": "2.0", "method": "state", "id": 1},
        {"jsonrpc": "2.0", "method": "state", "id": 2},
    ]
    resp = dispatch(batch, {"state": _state_executor})
    assert resp == [
        {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 1},
        {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 2},
    ]


def test_dispatch_batch_with_notification_omits_its_response() -> None:
    """A batch containing a notification responds only for the requests."""
    batch = [
        {"jsonrpc": "2.0", "method": "state", "id": 1},
        {"jsonrpc": "2.0", "method": "state"},
    ]
    resp = dispatch(batch, {"state": _state_executor})
    assert resp == [{"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 1}]


def test_dispatch_batch_all_notifications_gets_no_response() -> None:
    """A batch of only notifications gets no response.

    The spec says the server MUST NOT reply to notifications and MUST NOT
    return an empty array.
    """
    resp = dispatch([{"jsonrpc": "2.0", "method": "state"}], {"state": _state_executor})
    assert resp is None


def test_dispatch_empty_batch_gets_bare_invalid_request() -> None:
    """An empty batch is answered with a single (bare) Response object.

    The spec's own example shows a bare object, not an array.
    """
    resp = dispatch([], {"state": _state_executor})
    assert resp == {
        "jsonrpc": "2.0",
        "error": {"code": -32600, "message": "a batch must not be empty"},
        "id": None,
    }


def test_dispatch_batch_mixed_valid_and_invalid() -> None:
    """A batch with a malformed element responds per element: result, then error."""
    batch = [
        {"jsonrpc": "2.0", "method": "state", "id": 1},
        "junk",
    ]
    resp = dispatch(batch, {"state": _state_executor})
    assert resp is not None
    assert isinstance(resp, list)
    assert len(resp) == 2
    assert resp[0]["result"] == {"state": "SLIDESHOW"}
    assert resp[1]["error"]["code"] == -32600
    assert resp[1]["id"] is None


# --- param helpers -----------------------------------------------------------


def test_require_int_accepts_int_and_rejects_missing_and_wrong_type() -> None:
    """require_int returns the value for an int and raises -32602 otherwise."""
    from piframe.ipc import require_int

    assert require_int({"x": 5}, "x") == 5
    with pytest.raises(IpcError) as exc:
        require_int({}, "x")
    assert exc.value.code == -32602
    assert "x" in exc.value.message
    with pytest.raises(IpcError) as exc:
        require_int({"x": "5"}, "x")
    assert exc.value.code == -32602
    with pytest.raises(IpcError):
        require_int({"x": True}, "x")


def test_require_str_rejects_missing_and_wrong_type() -> None:
    """require_str returns the value for a string and raises -32602 otherwise."""
    from piframe.ipc import require_str

    assert require_str({"p": "/tmp/x"}, "p") == "/tmp/x"
    with pytest.raises(IpcError) as exc:
        require_str({}, "p")
    assert exc.value.code == -32602
    with pytest.raises(IpcError):
        require_str({"p": 3}, "p")


def test_optional_int_uses_default_and_validates_when_present() -> None:
    """optional_int returns the default when absent and validates a present value."""
    from piframe.ipc import optional_int

    assert optional_int({}, "ms", 300) == 300
    assert optional_int({"ms": 50}, "ms", 300) == 50
    with pytest.raises(IpcError) as exc:
        optional_int({"ms": "50"}, "ms", 300)
    assert exc.value.code == -32602


def test_require_scalar_accepts_numbers_and_strings() -> None:
    """require_scalar accepts any number or string (config values) and rejects the rest."""
    from piframe.ipc import require_scalar

    assert require_scalar({"v": 5}, "v") == 5
    assert require_scalar({"v": 5.5}, "v") == 5.5
    assert require_scalar({"v": "s"}, "v") == "s"
    assert require_scalar({"v": True}, "v") is True
    with pytest.raises(IpcError) as exc:
        require_scalar({}, "v")
    assert exc.value.code == -32602
    with pytest.raises(IpcError):
        require_scalar({"v": [1]}, "v")


# --- socket server -----------------------------------------------------------


def _client(path: Path) -> socket.socket:
    """Connect a Unix-socket client to *path*."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(str(path))
    return s


def _roundtrip(server: IpcServer, client: socket.socket, line: str) -> object:
    """Send one line, run main-loop iterations until the response arrives, decode it.

    The test thread plays the app's main loop: each iteration polls the
    server's queue, dispatches, and sends the response through the server.
    Returns the decoded response, or None when the connection closed without
    one (a notification).
    """
    client.sendall((line + "\n").encode())
    client.setblocking(False)
    data = b""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        item = server.poll()
        if item is not None:
            parsed, conn = item
            server.respond(conn, server.handle(parsed))
        try:
            chunk = client.recv(4096)
        except BlockingIOError:
            chunk = None
        if chunk is None:
            time.sleep(0.01)
            continue
        if not chunk:
            return json.loads(data) if data else None
        data += chunk
        if data.endswith(b"\n"):
            return json.loads(data)
    raise AssertionError(f"no response within 5s; got {data!r}")


def test_server_binds_socket_0600(tmp_path: Path) -> None:
    """The server binds its socket at the given path with mode 0600."""
    path = tmp_path / "piframe.sock"
    server = IpcServer(path, {"state": _state_executor})
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_ISSOCK(path.stat().st_mode)
    finally:
        server.stop()


def test_server_unlinks_stale_socket(tmp_path: Path) -> None:
    """A stale regular file at the socket path is replaced by the socket."""
    path = tmp_path / "piframe.sock"
    path.write_text("stale")
    server = IpcServer(path, {"state": _state_executor})
    try:
        assert stat.S_ISSOCK(path.stat().st_mode)
    finally:
        server.stop()


def test_server_roundtrip_request(tmp_path: Path) -> None:
    """A request line gets a result response echoing the id."""
    server = IpcServer(tmp_path / "piframe.sock", {"state": _state_executor})
    try:
        client = _client(tmp_path / "piframe.sock")
        try:
            resp = _roundtrip(server, client, '{"jsonrpc": "2.0", "method": "state", "id": 7}')
        finally:
            client.close()
        assert resp == {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 7}
    finally:
        server.stop()


def test_server_parse_error_response(tmp_path: Path) -> None:
    """A malformed line gets a -32700 parse error answered by the accept thread."""
    server = IpcServer(tmp_path / "piframe.sock", {"state": _state_executor})
    try:
        client = _client(tmp_path / "piframe.sock")
        try:
            resp = _roundtrip(server, client, "this is not json")
        finally:
            client.close()
        assert resp is not None
        assert isinstance(resp, dict)
        assert resp["error"]["code"] == -32700
        assert resp["id"] is None
    finally:
        server.stop()


def test_server_notification_gets_no_response(tmp_path: Path) -> None:
    """A notification is executed but gets no response: the connection just closes."""
    calls: list[int] = []

    def run(params: dict) -> dict:
        calls.append(1)
        return {}

    server = IpcServer(tmp_path / "piframe.sock", {"run": run})
    try:
        client = _client(tmp_path / "piframe.sock")
        try:
            resp = _roundtrip(server, client, '{"jsonrpc": "2.0", "method": "run"}')
        finally:
            client.close()
        assert resp is None
        assert calls == [1]
    finally:
        server.stop()


def test_server_batch_response(tmp_path: Path) -> None:
    """A batch line gets an array response in request order."""
    server = IpcServer(tmp_path / "piframe.sock", {"state": _state_executor})
    try:
        client = _client(tmp_path / "piframe.sock")
        try:
            resp = _roundtrip(
                server,
                client,
                '[{"jsonrpc": "2.0", "method": "state", "id": 1},'
                ' {"jsonrpc": "2.0", "method": "state", "id": 2}]',
            )
        finally:
            client.close()
        assert resp == [
            {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 1},
            {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 2},
        ]
    finally:
        server.stop()


def test_server_closes_connection_after_response(tmp_path: Path) -> None:
    """The connection is closed after the response (one request per connection)."""
    server = IpcServer(tmp_path / "piframe.sock", {"state": _state_executor})
    try:
        client = _client(tmp_path / "piframe.sock")
        _roundtrip(server, client, '{"jsonrpc": "2.0", "method": "state", "id": 1}')
        client.setblocking(True)
        assert client.recv(4096) == b""
        client.close()
    finally:
        server.stop()


def test_server_stop_removes_socket_and_refuses_new_connections(tmp_path: Path) -> None:
    """stop() unlinks the socket file and closes the listener, so new connections fail."""
    path = tmp_path / "piframe.sock"
    server = IpcServer(path, {"state": _state_executor})
    server.stop()
    assert not path.exists()
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        with pytest.raises(FileNotFoundError):
            client.connect(str(path))
    finally:
        client.close()


def test_server_oversized_line_gets_parse_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An oversized line gets a -32700 parse error and a closed connection.

    A runaway client must not grow the accept thread's memory.
    """
    import piframe.ipc as ipc_mod

    monkeypatch.setattr(ipc_mod, "_MAX_LINE", 64)
    server = IpcServer(tmp_path / "piframe.sock", {"state": _state_executor})
    try:
        client = _client(tmp_path / "piframe.sock")
        try:
            client.sendall(b"{" + b"x" * 200 + b"\n")
            data = b""
            while not data.endswith(b"\n"):
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            resp = json.loads(data)
        finally:
            client.close()
        assert resp["error"]["code"] == -32700
        assert resp["id"] is None
    finally:
        server.stop()


def test_server_stalled_client_does_not_block_the_accept_loop(tmp_path: Path) -> None:
    """A stalled client is closed after the read timeout.

    The accept loop still services new connections afterwards.
    """
    server = IpcServer(tmp_path / "piframe.sock", {"state": _state_executor}, recv_timeout=0.5)
    try:
        stalled = _client(tmp_path / "piframe.sock")
        time.sleep(1.0)  # let the accept loop time out on the stalled client
        client = _client(tmp_path / "piframe.sock")
        try:
            resp = _roundtrip(server, client, '{"jsonrpc": "2.0", "method": "state", "id": 1}')
        finally:
            client.close()
        assert resp == {"jsonrpc": "2.0", "result": {"state": "SLIDESHOW"}, "id": 1}
        stalled.close()
    finally:
        server.stop()
