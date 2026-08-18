"""Tests for the App entry point: PID-file lifecycle and headless boot."""

from __future__ import annotations

import os
import sys
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
    """Acquiring the PID file writes the PID and holds an exclusive lock."""
    fd = acquire_pid_file(pid_file)
    try:
        assert pid_file.read_text().strip() == str(os.getpid())
        with pytest.raises(SystemExit):
            acquire_pid_file(pid_file)
    finally:
        os.close(fd)
    # Closing the fd releases the lock: acquisition succeeds again.
    fd = acquire_pid_file(pid_file)
    os.close(fd)


def test_app_boots_headless_with_local_provider(
    pid_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The app boots with the dummy video driver and a local-provider config."""
    config = tmp_path / "config.toml"
    config.write_text(
        "[app]\n"
        "mock_wifi = true\n"
        "\n"
        "[sync]\n"
        'provider = "local"\n'
        f'source_dir = "{REPO_ROOT / "tests" / "fixtures" / "stock"}"\n'
    )
    monkeypatch.setattr(app_module, "PID_FILE", str(pid_file))
    monkeypatch.setattr(app_module, "CONFIG_PATH", config)
    monkeypatch.setattr(sys, "argv", ["slideshow", "--windowed"])

    app = App()
    try:
        assert pid_file.read_text().strip() == str(os.getpid())
        assert app._screen.get_size() == (1280, 800)
    finally:
        os.close(app._pid_fd)
