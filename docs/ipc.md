# IPC API

The app exposes a JSON-RPC 2.0 command API on a Unix socket so external
tools — and coding agents — can inspect and drive a running frame: read
state, tap and swipe the UI, take screenshots, change settings, trigger a
sync, and quit.

## Availability

The API is off by default. Enable it in `config.toml`:

```toml
[ipc]
enabled = true
```

or set the environment variable `PIFRAME_IPC__ENABLED=1` (or `true`) before
launch. The devcontainer template enables it by default
(`config.devcontainer.toml`), so the API is available out of the box in the
devcontainer.

At startup the app logs one line naming the API's state:
`IPC: listening on <path>` when bound, `IPC: disabled by config`, or
`IPC: enabled but unavailable (...)` when the bind failed.

## Socket path

The socket is `piframe.sock` (mode 0600) in the per-user runtime dir:

- `$XDG_RUNTIME_DIR/piframe.sock` when the session has a private
  `XDG_RUNTIME_DIR` (on the Pi: `/run/user/1000/piframe.sock`)
- `~/.local/piframe/piframe.sock` otherwise (e.g. the devcontainer)

Only the app's user can connect.

## The client

The documented entry point is:

```bash
bash eng/ipc.sh <command> [args]
```

It runs the `piframe-ipc` console script through uv, so no Python
environment is needed beyond the project's. The client resolves the socket
the same way the app resolves its runtime dir (the first existing candidate
location), so it works from any session of the app's user.

Options: `--socket PATH` (override the socket) and `--timeout SECONDS`
(read timeout, default 90).

Exit codes:

| Exit | Meaning |
|------|---------|
| 0 | success; the result is printed as JSON (if the method has one) |
| 1 | transport failure: no server at the socket, or the read timed out |
| 2 | usage error: unknown command or bad argument |
| 3 | protocol error: the server answered with an error (see error codes) |

## Wire protocol

- Framing: one newline-delimited JSON-RPC 2.0 request per connection; the
  server closes after the response. `quit` is a notification (no response).
- Request: `{"jsonrpc": "2.0", "method": "<name>", "params": {...}, "id": 1}`
- Response: `{"jsonrpc": "2.0", "result": ..., "id": 1}` or
  `{"jsonrpc": "2.0", "error": {"code": ..., "message": ...}, "id": 1}`

Error codes:

| Code | Meaning |
|------|---------|
| -32700 | parse error (the line is not JSON) |
| -32600 | invalid request (bad envelope) |
| -32601 | method not found |
| -32602 | invalid params (missing or wrong type) |
| -32603 | internal error (the executor raised) |

## Methods

| Method | Params | Result |
|--------|--------|--------|
| `state` | — | `{"state": "<AppState>"}` — e.g. `SLIDESHOW`, `OVERLAY` |
| `tap` | `x`, `y` (int) | `{}` |
| `swipe` | `x`, `y`, `dx`, `dy` (int); `ms` (int, default 300, max 60000) | `{}` |
| `play_pause` | — | `{"paused": <bool>}` |
| `prev` | — | `{}` |
| `next` | — | `{}` |
| `screenshot` | `path` (str) | `{}` — the file is written to `path` |
| `quit` | — | none (notification; the process exits before any response) |
| `set_config` | `section` (str), `key` (str), `value` (JSON scalar) | `{}` |
| `trigger_sync` | — | `{}` |

## Examples

```bash
bash eng/ipc.sh state
bash eng/ipc.sh screenshot --path /tmp/view.png
bash eng/ipc.sh swipe 100 200 0 500 --ms 1500
bash eng/ipc.sh set_config display interval 12
bash eng/ipc.sh trigger_sync
bash eng/ipc.sh quit
```

## Speaking the protocol directly

If you need the raw protocol (e.g. from a test), connect to the socket,
send one request line, read one response line, and close:

```python
import json
import socket

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.connect("/run/user/1000/piframe.sock")
s.sendall(json.dumps({"jsonrpc": "2.0", "method": "state", "id": 1}).encode() + b"\n")
print(s.recv(4096))
s.close()
```
