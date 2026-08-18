"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

# Must be set before any pygame import
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def pygame_init() -> Generator[None]:
    """Initialise pygame for the test session."""
    pygame.init()
    pygame.display.set_mode((1280, 800))
    yield
    pygame.quit()


@pytest.fixture(autouse=True)
def clean_piframe_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove PIFRAME_* env vars so default-value assertions are hermetic."""
    for name in list(os.environ):
        if name.startswith("PIFRAME_"):
            monkeypatch.delenv(name)


@pytest.fixture
def mock_backlight() -> Generator[MagicMock]:
    """Mock the sysfs backlight file for testing."""
    with patch("piframe.backlight.open", MagicMock()) as m:
        yield m


@pytest.fixture
def mock_nmcli() -> Generator[MagicMock]:
    """Return a mock that replaces subprocess.run inside WifiManager."""
    with patch("piframe.wifi_manager.subprocess.run") as m:
        yield m
