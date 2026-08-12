"""Unit tests for DI modules."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.modules import CacheModule, PlayerModule, SyncModule, WifiModule
from piframe.photo_cache import PhotoCache
from piframe.sync_service import SyncService
from piframe.wifi_manager import MockWifiManager, WifiManager


@pytest.fixture(scope="module", autouse=True)
def pg() -> None:
    """Initialise pygame with a dummy display."""
    pygame.init()
    pygame.display.set_mode((1280, 800))


@pytest.fixture
def config(tmp_path: Path) -> ConfigStore:
    """Return a ConfigStore backed by a temp config file."""
    path = tmp_path / "config.toml"
    path.write_text("[slideshow]\ninterval = 30\n")
    return ConfigStore(path)


def test_wifi_module_selects_real(config: ConfigStore) -> None:
    """Wifi module selects real."""
    """WifiModule returns WifiManager when mock_wifi is False."""
    wifi = WifiModule().create(config)
    assert isinstance(wifi, WifiManager)


def test_wifi_module_selects_mock(config: ConfigStore) -> None:
    """Wifi module selects mock."""
    """WifiModule returns MockWifiManager when mock_wifi is True."""
    config.set("app", "mock_wifi", True)
    wifi = WifiModule().create(config)
    assert isinstance(wifi, MockWifiManager)


def test_cache_module_sets_cache_dir(config: ConfigStore) -> None:
    """Cache module sets cache dir."""
    """CacheModule passes the configured cache_dir to PhotoCache."""
    cache = CacheModule().create(config)
    assert cache._cache_dir == Path("/home/frame/.cache/framesync")


def test_cache_module_sets_screen_size(config: ConfigStore) -> None:
    """Cache module sets screen size."""
    """CacheModule passes the screen size constants to PhotoCache."""
    cache = CacheModule().create(config)
    assert cache._w == 1280
    assert cache._h == 800


def test_sync_module_creates_service(config: ConfigStore) -> None:
    """Sync module creates service."""
    """SyncModule returns a SyncService instance."""
    sync = SyncModule().create(config)
    assert isinstance(sync, SyncService)


def test_player_module_passes_deps(config: ConfigStore) -> None:
    """Player module passes deps."""
    """PlayerModule wires cache and assets into the SlideshowPlayer."""
    cache = MagicMock(spec=PhotoCache)
    assets = MagicMock(spec=Assets)
    player = PlayerModule().create(config, cache=cache, assets=assets)
    assert player._cache is cache
    assert player._assets is assets
