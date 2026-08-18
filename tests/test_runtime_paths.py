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
    """The XDG runtime dir is used when it is set and exists."""
    d = tmp_path / "runtime"
    d.mkdir()
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


def test_resolve_uses_existing_fallback_as_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An existing fallback dir is used as-is: its mode is not changed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    d = tmp_path / ".local" / "piframe"
    d.mkdir(parents=True)
    d.chmod(0o755)
    assert runtime_paths.resolve_runtime_dir() == d
    assert stat.S_IMODE(d.stat().st_mode) == 0o755


def test_socket_and_pid_file_paths(tmp_path: Path) -> None:
    """The artifact paths are the resolved dir plus fixed file names."""
    assert runtime_paths.socket_path(tmp_path) == tmp_path / "piframe.sock"
    assert runtime_paths.pid_file_path(tmp_path) == tmp_path / "slideshow.pid"
