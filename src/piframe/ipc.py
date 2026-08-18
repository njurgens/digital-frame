"""The IPC API: a JSON-RPC 2.0 command server on a Unix socket.

The wire protocol is JSON-RPC 2.0 (jsonrpc.org), newline-delimited: one
request line per connection, one response line back (or none for a
notification).  The protocol layer (envelope validation, dispatch, response
construction, the standard error codes) is pure functions over the parsed
request, unit-testable without a socket; the ``IpcServer`` adds the socket:
an accept thread that reads and parses one line per connection, and a queue
the app's main loop drains to execute commands and send responses.

The module never imports the app: the app constructs the server and injects
the executor callables (the dispatch table), so the import arrow points only
app→ipc and the module stays importable and testable without a display.
"""

from __future__ import annotations

import json
import os
import queue
import socket
import threading
from collections.abc import Callable, Mapping
from pathlib import Path

#: JSON-RPC 2.0 standard error codes.
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

#: An executor: takes the request's named params and returns the result value.
Executor = Callable[[dict], object]


class IpcError(Exception):
    """An executor-reported error carrying a JSON-RPC error code.

    Executors raise this to report a protocol-level failure (e.g. invalid
    params); the dispatch layer turns it into an error response with the
    given code.  Any other exception becomes an internal error (-32603).
    """

    def __init__(self, code: int, message: str) -> None:
        """Create an error with the given JSON-RPC error code and message."""
        super().__init__(message)
        self.code = code
        self.message = message


def make_response(rid: object, result: object) -> dict:
    """A success response: ``{"jsonrpc", "result", "id"}``."""
    return {"jsonrpc": "2.0", "result": result, "id": rid}


def make_error(rid: object, code: int, message: str) -> dict:
    """An error response: ``{"jsonrpc", "error": {"code", "message"}, "id"}``."""
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": rid}


def _is_valid_id(rid: object) -> bool:
    """True if *rid* is a valid JSON-RPC id: a string, a number, or null."""
    return (
        rid is None
        or isinstance(rid, str)
        or (isinstance(rid, (int, float)) and not isinstance(rid, bool))
    )


def _error_id(obj: dict) -> object:
    """The id to echo in an error response: the request's if valid, else null.

    The spec requires a null response id when the request's id could not be
    determined (absent or malformed).
    """
    if "id" not in obj:
        return None
    rid = obj["id"]
    return rid if _is_valid_id(rid) else None


def _dispatch_element(obj: object, executors: Mapping[str, Executor]) -> dict | None:
    """Validate, dispatch, and build the response for one request object.

    A notification (a request object without an id member) never gets a
    response, whatever the outcome: the spec says the server MUST NOT reply
    to a notification.
    """
    if not isinstance(obj, dict):
        return make_error(None, INVALID_REQUEST, "a request must be a JSON object")
    response = _dispatch_request(obj, executors)
    if "id" not in obj:
        return None
    return response


def _dispatch_request(obj: dict, executors: Mapping[str, Executor]) -> dict:
    """Validate and dispatch one request object; always returns a response."""
    if obj.get("jsonrpc") != "2.0":
        return make_error(_error_id(obj), INVALID_REQUEST, "jsonrpc must be '2.0'")
    method = obj.get("method")
    if not isinstance(method, str):
        return make_error(_error_id(obj), INVALID_REQUEST, "method must be a string")
    params = obj.get("params", {})
    if not isinstance(params, (list, dict)):
        return make_error(_error_id(obj), INVALID_REQUEST, "params must be an array or an object")
    if "id" in obj and not _is_valid_id(obj["id"]):
        return make_error(None, INVALID_REQUEST, "id must be a string, a number, or null")
    rid = obj.get("id")
    try:
        executor = executors.get(method)
        if executor is None:
            raise IpcError(METHOD_NOT_FOUND, f"method not found: {method}")
        if isinstance(params, list):
            # This API's methods take named (object) params.
            raise IpcError(INVALID_PARAMS, "params must be an object of named values")
        result = executor(params)
    except IpcError as e:
        return make_error(rid, e.code, e.message)
    except Exception as e:
        return make_error(rid, INTERNAL_ERROR, str(e))
    return make_response(rid, result)


def dispatch(parsed: object, executors: Mapping[str, Executor]) -> dict | list[dict] | None:
    """Run the JSON-RPC 2.0 request/response pipeline over a parsed request.

    *parsed* is the decoded JSON value of one line: a request object, a batch
    (a non-empty array of request objects), or a value that is not a request
    (which yields an invalid-request error).  Returns the response — an object
    for a single request, an array for a batch — or None when no response is
    due (a notification, or a batch of only notifications).
    """
    if isinstance(parsed, list):
        if not parsed:
            # The spec's own example: an empty batch is answered with a
            # single Response object, not an array.
            return make_error(None, INVALID_REQUEST, "a batch must not be empty")
        responses = [
            response
            for response in (_dispatch_element(element, executors) for element in parsed)
            if response is not None
        ]
        # A batch of only notifications produces no Response objects: the spec
        # says the server MUST NOT reply to notifications and MUST NOT return
        # an empty array — send nothing.
        return responses if responses else None
    return _dispatch_element(parsed, executors)


def require_int(params: dict, name: str) -> int:
    """``params[name]`` as an int, or an invalid-params error."""
    if name not in params:
        raise IpcError(INVALID_PARAMS, f"missing param: {name}")
    value = params[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise IpcError(INVALID_PARAMS, f"param {name} must be an integer")
    return value


def require_str(params: dict, name: str) -> str:
    """``params[name]`` as a string, or an invalid-params error."""
    if name not in params:
        raise IpcError(INVALID_PARAMS, f"missing param: {name}")
    value = params[name]
    if not isinstance(value, str):
        raise IpcError(INVALID_PARAMS, f"param {name} must be a string")
    return value


def optional_int(params: dict, name: str, default: int) -> int:
    """``params[name]`` as an int, or *default* when absent."""
    value = params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise IpcError(INVALID_PARAMS, f"param {name} must be an integer")
    return value


def require_scalar(params: dict, name: str) -> float | str | bool:
    """``params[name]`` as a number or string (a config value), or an error."""
    if name not in params:
        raise IpcError(INVALID_PARAMS, f"missing param: {name}")
    value = params[name]
    if not isinstance(value, (int, float, str)):
        raise IpcError(INVALID_PARAMS, f"param {name} must be a number or a string")
    return value


#: Max bytes of one request line before the accept thread answers -32700 and
#: closes the connection (a runaway client must not grow its memory).
_MAX_LINE = 1 << 20  # 1 MiB

#: Default read timeout (s) for an accepted connection: a client that
#: connects and stalls must not hold the accept loop.
_RECV_TIMEOUT = 30.0


class IpcServer:
    """The app's Unix-socket command server: one JSON-RPC request per connection.

    The accept thread reads one line per connection and parses it; a parse
    failure is answered and closed there (it needs no app state), otherwise
    the parsed request is queued with its connection.  The app's main loop
    calls :meth:`poll` each iteration, dispatches via :meth:`handle`, and
    sends the response via :meth:`respond` — the side that sends the
    response closes the connection, so the two sides cannot disagree about a
    connection's life.  The read is bounded: a stalled client is closed
    after the read timeout, and a line longer than the cap is answered
    -32700, so one client cannot hold the accept loop or its memory.
    """

    def __init__(
        self,
        socket_path: Path,
        executors: Mapping[str, Executor],
        recv_timeout: float = _RECV_TIMEOUT,
    ) -> None:
        """Bind *socket_path* (0600, unlinked first if stale) and start the accept thread."""
        self._socket_path = socket_path
        self._executors = dict(executors)
        self._recv_timeout = recv_timeout
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        try:
            os.unlink(self._socket_path)
        except FileNotFoundError:
            pass
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(self._socket_path))
        os.chmod(self._socket_path, 0o600)
        server.listen(5)
        server.settimeout(0.5)
        self._server = server
        self._stopping = False
        self._thread = threading.Thread(target=self._accept_loop, args=(server,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the accept thread, close the listener, and unlink the socket file.

        The file is removed on a clean stop so no stale socket survives; the
        next start's unlink-then-bind then has nothing to clean up.
        """
        self._stopping = True
        if self._server is not None:
            self._server.close()
            self._server = None
        try:
            self._socket_path.unlink()
        except FileNotFoundError:
            pass

    def poll(self) -> tuple[object, socket.socket] | None:
        """The next parsed request with its connection, or None if none is queued."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def handle(self, parsed: object) -> dict | list[dict] | None:
        """Validate, dispatch, and build the response for a parsed request."""
        return dispatch(parsed, self._executors)

    def respond(self, conn: socket.socket, response: dict | list[dict] | None) -> None:
        """Send *response* to *conn* and close it (a None response just closes)."""
        try:
            if response is not None:
                conn.sendall((json.dumps(response) + "\n").encode())
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _accept_loop(self, server: socket.socket) -> None:
        while not self._stopping:
            try:
                conn, _ = server.accept()
            except TimeoutError:
                continue  # no connection yet: re-check the stop flag
            except OSError:
                return  # the listening socket was closed (stop)
            try:
                conn.settimeout(self._recv_timeout)
                data = b""
                got = 0
                over = False
                while b"\n" not in data and not over:
                    try:
                        chunk = conn.recv(4096)
                    except TimeoutError:
                        break  # stalled: no data arrived within the timeout
                    if not chunk:
                        break
                    data += chunk
                    got += len(chunk)
                    if len(data) > _MAX_LINE:
                        over = True
                if over:
                    self.respond(conn, make_error(None, PARSE_ERROR, "line too long"))
                    continue
                if not got:
                    # The client connected and sent nothing: close without a
                    # response (there is no request to answer).
                    try:
                        conn.close()
                    except OSError:
                        pass
                    continue
                line = data.split(b"\n", 1)[0]
                try:
                    parsed = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self.respond(conn, make_error(None, PARSE_ERROR, "parse error"))
                    continue
                self._queue.put((parsed, conn))
            except Exception:
                try:
                    conn.close()
                except OSError:
                    pass
