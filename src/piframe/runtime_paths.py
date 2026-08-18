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
    """The per-user runtime dir (``$XDG_RUNTIME_DIR``) if it is usable.

    The directory must exist, be owned by the current user, and carry no
    group or other permission bits — the trust boundary for the 0600
    artifacts.  A misconfigured session environment (a foreign-owned or
    group/other-accessible dir) is treated as unavailable, so the caller
    falls back to the user-creatable dir instead.
    """
    env = os.environ.get("XDG_RUNTIME_DIR")
    if not env:
        return None
    d = Path(env)
    if not d.is_dir():
        return None
    st = d.stat()
    if st.st_uid != os.getuid() or st.st_mode & 0o077:
        return None
    return d


def fallback_dir() -> Path:
    """The user-creatable fallback dir: ``~/.local/piframe``."""
    return Path.home() / ".local" / "piframe"


def resolve_runtime_dir() -> Path:
    """The directory for the runtime artifacts: the runtime dir if available.

    Without a runtime dir (e.g. in a container without logind), the fallback
    dir is used: its mode is enforced to 0700 — created 0700 if absent,
    tightened if present (a looser pre-existing mode would let other local
    users plant files in the artifact dir) — and a warning names it.
    """
    d = runtime_dir()
    if d is not None:
        return d
    d = fallback_dir()
    if d.is_dir():
        try:
            os.chmod(d, 0o700)
        except OSError as e:
            # e.g. the dir is owned by another user (a shared $HOME): the
            # boundary cannot be enforced, so fail closed like the creation
            # branch does.
            raise OSError(f"cannot secure fallback runtime dir {d}: {e}") from e
    else:
        # Create the leaf directly at its final mode so it is never
        # group/other accessible, even for the instant between mkdir and
        # chmod (the parent is the standard ~/.local dir).
        try:
            d.parent.mkdir(parents=True, exist_ok=True)
            d.mkdir(mode=0o700)
        except OSError as e:
            raise OSError(f"cannot create fallback runtime dir {d}: {e}") from e
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
