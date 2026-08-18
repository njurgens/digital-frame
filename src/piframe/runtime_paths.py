"""Resolution of the per-user directory that holds the app's runtime artifacts.

The IPC socket and PID file live in the per-user 0700 runtime dir
(``$XDG_RUNTIME_DIR``) when it is available, and in the user-creatable
``~/.local/piframe`` fallback otherwise.  Both locations are private to the
app's user, so a 0600 artifact in either is unreadable and unredirectable by
other local users.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

#: File names of the runtime artifacts, shared by the app and eng/run.sh.
SOCKET_NAME = "piframe.sock"
PID_FILE_NAME = "slideshow.pid"


def runtime_dir() -> Path | None:
    """The per-user runtime dir (``$XDG_RUNTIME_DIR``) if set and present."""
    env = os.environ.get("XDG_RUNTIME_DIR")
    if not env:
        return None
    d = Path(env)
    return d if d.is_dir() else None


def fallback_dir() -> Path:
    """The user-creatable fallback dir: ``~/.local/piframe``."""
    return Path.home() / ".local" / "piframe"


def resolve_runtime_dir() -> Path:
    """The directory for the runtime artifacts: the runtime dir if available.

    Without a runtime dir (e.g. in a container without logind), the fallback
    dir is created 0700 if absent and used as-is if present, and a warning
    names it.
    """
    d = runtime_dir()
    if d is not None:
        return d
    d = fallback_dir()
    if not d.is_dir():
        d.mkdir(parents=True)
        os.chmod(d, 0o700)
        logging.warning(
            "XDG_RUNTIME_DIR is unavailable; using %s for the IPC socket and PID file",
            d,
        )
    return d


def socket_path(runtime_dir: Path) -> Path:
    """The IPC socket path inside *runtime_dir*."""
    return runtime_dir / SOCKET_NAME


def pid_file_path(runtime_dir: Path) -> Path:
    """The PID file path inside *runtime_dir*."""
    return runtime_dir / PID_FILE_NAME
