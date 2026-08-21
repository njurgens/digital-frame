"""Tests for runtime_paths: where the app's runtime artifacts live."""

from __future__ import annotations

import logging
import stat
from pathlib import Path

import pytest

from piframe import runtime_paths


def test_runtime_dir_returns_xdg_dir_when_it_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The XDG runtime dir is used when it is set, private, and owned."""
    d = tmp_path / "runtime"
    d.mkdir()
    d.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(d))
    assert runtime_paths.runtime_dir() == d


def test_runtime_dir_none_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unset XDG_RUNTIME_DIR means there is no runtime dir."""
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    assert runtime_paths.runtime_dir() is None


def test_runtime_dir_none_when_dir_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A set but missing XDG_RUNTIME_DIR is treated as absent."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "missing"))
    assert runtime_paths.runtime_dir() is None


def test_runtime_dir_rejects_group_or_other_accessible_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A runtime dir carrying group/other bits is treated as absent.

    A 0755 (or looser) dir is not private enough for the 0600 artifacts, so
    resolution falls back to the user-creatable dir.
    """
    d = tmp_path / "runtime"
    d.mkdir()
    d.chmod(0o755)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(d))
    assert runtime_paths.runtime_dir() is None


def test_fallback_dir_is_local_piframe(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fallback dir is ~/.local/piframe."""
    monkeypatch.setenv("HOME", "/fake/home")
    assert runtime_paths.fallback_dir() == Path("/fake/home/.local/piframe")


def test_resolve_uses_runtime_dir_when_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolution prefers the XDG runtime dir over the fallback."""
    d = tmp_path / "runtime"
    d.mkdir()
    d.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(d))
    assert runtime_paths.resolve_runtime_dir() == d


def test_resolve_creates_fallback_0700_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Without a runtime dir, the fallback is created 0700 and a warning names it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    with caplog.at_level(logging.WARNING):
        d = runtime_paths.resolve_runtime_dir()
    assert d == tmp_path / ".local" / "piframe"
    assert stat.S_IMODE(d.stat().st_mode) == 0o700
    assert any(str(tmp_path / ".local" / "piframe") in m for m in caplog.messages)


def test_resolve_tightens_existing_fallback_to_0700(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing fallback dir is tightened to 0700.

    A looser pre-existing mode would let other local users plant files in
    the artifact dir.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    d = tmp_path / ".local" / "piframe"
    d.mkdir(parents=True)
    d.chmod(0o755)
    assert runtime_paths.resolve_runtime_dir() == d
    assert stat.S_IMODE(d.stat().st_mode) == 0o700


def test_resolve_fails_closed_when_fallback_uncreatable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uncreatable fallback dir (unwritable ~/.local) fails closed.

    The error names the directory (F-2).
    """
    home = tmp_path / "home"
    (home / ".local").mkdir(parents=True)
    (home / ".local").chmod(0o555)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    with pytest.raises(OSError, match="cannot create fallback runtime dir"):
        runtime_paths.resolve_runtime_dir()


def test_resolve_fails_closed_when_existing_fallback_cannot_be_secured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing fallback dir that cannot be tightened fails closed.

    E.g. the dir is owned by another user; the error names the directory.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    d = tmp_path / ".local" / "piframe"
    d.mkdir(parents=True)

    def boom(path: object, mode: int) -> None:
        raise PermissionError(13, "Operation not permitted", str(path))

    monkeypatch.setattr(runtime_paths.os, "chmod", boom)
    with pytest.raises(OSError, match="cannot secure fallback runtime dir"):
        runtime_paths.resolve_runtime_dir()


def test_socket_and_pid_file_paths(tmp_path: Path) -> None:
    """The artifact paths are the resolved dir plus fixed file names."""
    assert runtime_paths.socket_path(tmp_path) == tmp_path / "piframe.sock"
    assert runtime_paths.pid_file_path(tmp_path) == tmp_path / "slideshow.pid"


def test_system_runtime_dir_is_run_user_uid(monkeypatch: pytest.MonkeyPatch) -> None:
    """The system runtime dir is /run/user/{uid} (XDG's default location)."""
    monkeypatch.setattr(runtime_paths.os, "getuid", lambda: 1000)
    assert runtime_paths.system_runtime_dir() == Path("/run/user/1000")


def test_candidate_dirs_other_is_fallback_when_primary_is_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A primary that is the system runtime dir probes the fallback."""
    monkeypatch.setattr(runtime_paths.os, "getuid", lambda: 1000)
    system = Path("/run/user/1000")
    fallback = tmp_path / "fallback"
    assert runtime_paths.candidate_dirs(system, fallback) == (system, fallback)


def test_candidate_dirs_other_is_system_when_primary_is_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A primary that is the fallback probes the system runtime dir."""
    monkeypatch.setattr(runtime_paths.os, "getuid", lambda: 1000)
    fallback = tmp_path / "fallback"
    assert runtime_paths.candidate_dirs(fallback, fallback) == (fallback, Path("/run/user/1000"))


def test_candidate_dirs_other_is_fallback_for_any_other_primary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A primary that is neither the system dir nor the fallback probes the fallback."""
    monkeypatch.setattr(runtime_paths.os, "getuid", lambda: 1000)
    custom = tmp_path / "custom"
    fallback = tmp_path / "fallback"
    assert runtime_paths.candidate_dirs(custom, fallback) == (custom, fallback)
