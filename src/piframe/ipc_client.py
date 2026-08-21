"""Client for the app's IPC command API: one JSON-RPC 2.0 request per connection.

The app's IPC server (see ipc.py) answers one newline-delimited JSON-RPC 2.0
request per connection and closes after the response.  This client mirrors
that: each call opens a fresh connection, sends one request line, reads one
response line (or none for a notification), and closes.  There is no session,
no batching, and no retry — a command that times out may still execute in the
app, so a retry would double-execute it.

The client resolves the socket the same way the app resolves its runtime dir
(runtime_paths.candidate_dirs): the first existing candidate wins, so an
agent that cannot see the app's XDG_RUNTIME_DIR still finds the socket in
the fallback dir.  The console script is ``piframe-ipc``; the documented
entry point is ``bash eng/ipc.sh`` (see docs/ipc.md).
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from piframe.runtime_paths import SOCKET_NAME, candidate_dirs, fallback_dir, resolve_runtime_dir

#: Default read timeout for one request, in seconds.
DEFAULT_TIMEOUT = 90.0

#: Default swipe duration in milliseconds (the server bounds it to 60000).
DEFAULT_SWIPE_MS = 300

#: Max bytes of one response line before the client gives up: mirrors the
#: server's request-line cap, so a hostile peer cannot exhaust the client's
#: memory by streaming a newline-less line for the full read timeout.
MAX_RESPONSE_LINE = 1 << 20  # 1 MiB


class IpcRpcError(Exception):
    """A server error response, carrying its JSON-RPC code and message."""

    def __init__(self, code: int, message: str) -> None:
        """Create an error with the given JSON-RPC code and message."""
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class IpcTransportError(Exception):
    """A transport failure: connect, read, or framing (the app may be fine)."""


def resolve_socket_path() -> Path:
    """The socket to connect to: the first existing candidate, else the resolved dir's path.

    The candidates are the app's two artifact locations (the resolved runtime
    dir and its cross-location partner), probed in that order; when neither
    holds a socket the resolved dir's path is returned, so a connect failure
    names the location the app would use.
    """
    resolved = resolve_runtime_dir()
    for d in candidate_dirs(resolved, fallback_dir()):
        p = d / SOCKET_NAME
        if p.exists():
            return p
    return resolved / SOCKET_NAME


class IpcClient:
    """One JSON-RPC 2.0 request per connection against the app's IPC server."""

    def __init__(self, socket_path: Path | None = None, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Connect to *socket_path* (resolved like the app when None)."""
        self._socket_path = socket_path if socket_path is not None else resolve_socket_path()
        self._timeout = timeout

    @property
    def socket_path(self) -> Path:
        """The socket this client connects to."""
        return self._socket_path

    def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        notification: bool = False,
    ) -> Any:
        """Send one request on a fresh connection and return its result.

        A notification (no id) returns None: the server never answers one.
        Raises IpcRpcError for a server error response and IpcTransportError
        for a connect, read, or framing failure.
        """
        request: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            request["params"] = params
        if not notification:
            request["id"] = 1
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(self._timeout)
                s.connect(str(self._socket_path))
                s.sendall((json.dumps(request) + "\n").encode())
                if notification:
                    return None
                data = self._read_response(s)
        except OSError as err:
            raise IpcTransportError(f"{self._socket_path}: {err}") from err
        return self._parse_response(data)

    def _read_response(self, s: socket.socket) -> bytes:
        """Read the response line (until the newline, the cap, or the server closes)."""
        buf = b""
        while b"\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            if len(buf) > MAX_RESPONSE_LINE:
                raise IpcTransportError(f"{self._socket_path}: response line exceeds 1 MiB")
        return buf

    def _parse_response(self, data: bytes) -> Any:
        """The result of a well-formed response, or a transport/rpc error."""
        line = data.strip()
        if not line:
            raise IpcTransportError(
                f"{self._socket_path}: the server closed the connection without a response"
            )
        try:
            response = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            raise IpcTransportError(
                f"{self._socket_path}: unparseable response from the server: {err}"
            ) from err
        if not isinstance(response, dict):
            raise IpcTransportError(f"{self._socket_path}: the response is not a JSON object")
        if "error" in response:
            err = response["error"]
            if not isinstance(err, dict):
                raise IpcTransportError(
                    f"{self._socket_path}: malformed error object in the response"
                )
            try:
                code = int(err.get("code", 0))
            except (TypeError, ValueError):
                raise IpcTransportError(
                    f"{self._socket_path}: malformed error object in the response"
                ) from None
            raise IpcRpcError(code, str(err.get("message", "")))
        if "result" not in response:
            raise IpcTransportError(
                f"{self._socket_path}: the response has neither a result nor an error"
            )
        return response["result"]

    # --- one typed method per JSON-RPC method --------------------------------

    def state(self) -> dict[str, Any]:
        """The current app state: {"state": <AppState name>}."""
        return self.call("state")

    def tap(self, x: int, y: int) -> dict[str, Any]:
        """Post a synthetic tap (down + up) at (x, y)."""
        return self.call("tap", {"x": x, "y": y})

    def swipe(
        self, x: int, y: int, dx: int, dy: int, ms: int = DEFAULT_SWIPE_MS
    ) -> dict[str, Any]:
        """Post a synthetic swipe from (x, y) by (dx, dy) over ms milliseconds."""
        return self.call("swipe", {"x": x, "y": y, "dx": dx, "dy": dy, "ms": ms})

    def play_pause(self) -> dict[str, Any]:
        """Toggle playback; returns {"paused": <bool>}."""
        return self.call("play_pause")

    def prev(self) -> dict[str, Any]:
        """Go back one slide."""
        return self.call("prev")

    def next(self) -> dict[str, Any]:
        """Skip to the next slide."""
        return self.call("next")

    def screenshot(self, path: str) -> dict[str, Any]:
        """Save the current screen to *path*."""
        return self.call("screenshot", {"path": path})

    def quit(self) -> None:
        """Quit the app (a notification: the process exits before any response)."""
        self.call("quit", notification=True)

    def set_config(
        self, section: str, key: str, value: str | int | float | bool
    ) -> dict[str, Any]:
        """Set a config value (a JSON scalar), then refresh the dependent UI."""
        return self.call("set_config", {"section": section, "key": key, "value": value})

    def trigger_sync(self) -> dict[str, Any]:
        """Trigger a photo sync."""
        return self.call("trigger_sync")


def _parse_scalar(text: str) -> str | int | float | bool:
    """A JSON scalar (bool, number, or string), or a usage error."""
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError as err:
        raise argparse.ArgumentTypeError(f"not a JSON scalar: {text} ({err})") from err
    if value is None or isinstance(value, (dict, list)):
        raise argparse.ArgumentTypeError(f"not a JSON scalar: {text}")
    return value


@dataclass(frozen=True)
class _CommandSpec:
    """One CLI command: its help text, its arguments, and its handler.

    Each argument spec is (name, type, default, help): a leading dash marks
    an option (a None default makes it required); otherwise it is positional.
    """

    help: str
    args: tuple[tuple[str, Callable[[str], object], object, str | None], ...]
    handler: Callable[[IpcClient, argparse.Namespace], Any]


#: The client's commands, one per JSON-RPC method.  This is the single
#: source of truth for the CLI: the subparsers and the dispatcher are both
#: built from it, and it must match the app's IPC_METHOD_NAMES and
#: docs/ipc.md's method table (a test pins all three).
_COMMANDS: dict[str, _CommandSpec] = {
    "state": _CommandSpec("report the current app state", (), lambda c, a: c.state()),
    "tap": _CommandSpec(
        "post a synthetic tap at (x, y)",
        (("x", int, None, None), ("y", int, None, None)),
        lambda c, a: c.tap(a.x, a.y),
    ),
    "swipe": _CommandSpec(
        "post a synthetic swipe from (x, y) by (dx, dy)",
        (
            ("x", int, None, None),
            ("y", int, None, None),
            ("dx", int, None, None),
            ("dy", int, None, None),
            (
                "--ms",
                int,
                DEFAULT_SWIPE_MS,
                f"duration in milliseconds (default {DEFAULT_SWIPE_MS})",
            ),
        ),
        lambda c, a: c.swipe(a.x, a.y, a.dx, a.dy, ms=a.ms),
    ),
    "play_pause": _CommandSpec("toggle playback", (), lambda c, a: c.play_pause()),
    "prev": _CommandSpec("go back one slide", (), lambda c, a: c.prev()),
    "next": _CommandSpec("skip to the next slide", (), lambda c, a: c.next()),
    "screenshot": _CommandSpec(
        "save the current screen to a file",
        (("--path", str, None, "where to save the screenshot"),),
        lambda c, a: c.screenshot(a.path),
    ),
    "quit": _CommandSpec("quit the app (a notification: no response)", (), lambda c, a: c.quit()),
    "set_config": _CommandSpec(
        "set a config value (a JSON scalar)",
        (
            ("section", str, None, None),
            ("key", str, None, None),
            (
                "value",
                _parse_scalar,
                None,
                'the new value as a JSON scalar (e.g. 17, true, "night")',
            ),
        ),
        lambda c, a: c.set_config(a.section, a.key, a.value),
    ),
    "trigger_sync": _CommandSpec("trigger a photo sync", (), lambda c, a: c.trigger_sync()),
}

#: The client's command names, derived from the spec above.
COMMANDS: frozenset[str] = frozenset(_COMMANDS)


def _build_parser() -> argparse.ArgumentParser:
    """The piframe-ipc argument parser: one subcommand per JSON-RPC method."""
    parser = argparse.ArgumentParser(
        prog="piframe-ipc",
        description="Drive the running Pi Frame app over its IPC command API (see docs/ipc.md).",
    )
    parser.add_argument(
        "--socket",
        type=Path,
        default=None,
        metavar="PATH",
        help="the socket to connect to (default: resolved like the app's runtime dir)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"read timeout in seconds (default {DEFAULT_TIMEOUT:g})",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")
    for name, spec in _COMMANDS.items():
        p = sub.add_parser(name, help=spec.help)
        for arg_name, arg_type, default, arg_help in spec.args:
            if arg_name.startswith("-"):
                if default is None:
                    p.add_argument(arg_name, type=arg_type, required=True, help=arg_help)
                else:
                    p.add_argument(arg_name, type=arg_type, default=default, help=arg_help)
            else:
                p.add_argument(arg_name, type=arg_type, help=arg_help)
    return parser


def _run_command(client: IpcClient, args: argparse.Namespace) -> Any:
    """Dispatch the parsed subcommand to its handler."""
    spec = _COMMANDS.get(args.command)
    if spec is None:
        raise AssertionError(f"unhandled command: {args.command}")
    return spec.handler(client, args)


def main(argv: Sequence[str] | None = None) -> int:
    """The piframe-ipc console script: run one command and exit 0/1/2/3.

    Exit codes: 0 success, 1 transport failure (no server, timeout),
    2 usage error (bad subcommand or argument), 3 protocol error (the
    server answered with an error).
    """
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        client = IpcClient(socket_path=args.socket, timeout=args.timeout)
        result = _run_command(client, args)
    except (IpcTransportError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except IpcRpcError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    if result is not None:
        print(json.dumps(result))
    return 0
