"""Unit tests for DI modules."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

from piframe.album import Album
from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.modules import (
    CacheModule,
    PlayerModule,
    ProviderModule,
    SyncModule,
    WifiModule,
)
from piframe.photo_cache import PhotoCache
from piframe.providers import (
    GooglePhotosProvider,
    LocalProvider,
    OneDriveProvider,
)
from piframe.sync_service import SyncService
from piframe.types import SyncStatus
from piframe.wifi_manager import MockWifiManager, WifiManager


class _StubAlbumProvider:
    """Test double for the album provider protocol."""

    @property
    def storage_dir(self) -> Path | None:
        return None

    def sync(self) -> Album:
        return Album()

    def album(self) -> Album:
        return Album()

    def status(self) -> SyncStatus:
        return SyncStatus()

    def close(self) -> None:
        pass


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
    """CacheModule constructs a PhotoCache at the default surface cache dir."""
    cache = CacheModule().create(config)
    assert cache._cache_dir == Path.home() / ".cache" / "piframe" / "surfaces"


def test_cache_module_sets_screen_size(config: ConfigStore) -> None:
    """Cache module sets screen size."""
    """CacheModule passes the screen size constants to PhotoCache."""
    cache = CacheModule().create(config)
    assert cache._w == 1280
    assert cache._h == 800


def test_sync_module_creates_service(config: ConfigStore) -> None:
    """SyncModule returns a SyncService wired to the given provider."""
    provider = _StubAlbumProvider()
    sync = SyncModule().create(config, provider=provider)
    assert isinstance(sync, SyncService)
    assert sync.provider is provider
    sync.stop()


def test_player_module_passes_deps(config: ConfigStore) -> None:
    """PlayerModule wires provider, cache, and assets into the SlideshowPlayer."""
    provider = _StubAlbumProvider()
    cache = MagicMock(spec=PhotoCache)
    assets = MagicMock(spec=Assets)
    player = PlayerModule().create(config, provider=provider, cache=cache, assets=assets)
    assert player._provider is provider
    assert player._cache is cache
    assert player._assets is assets


def test_provider_module_selects_local(config: ConfigStore) -> None:
    """Provider module selects the local provider by default."""
    provider = ProviderModule().create(config)
    assert isinstance(provider, LocalProvider)


def test_provider_module_selects_onedrive(config: ConfigStore) -> None:
    """Provider module selects the OneDrive provider from config."""
    config.set("sync", "provider", "onedrive")
    provider = ProviderModule().create(config)
    assert isinstance(provider, OneDriveProvider)


def test_provider_module_selects_google(config: ConfigStore) -> None:
    """Provider module selects the Google stub from config."""
    config.set("sync", "provider", "google")
    provider = ProviderModule().create(config)
    assert isinstance(provider, GooglePhotosProvider)


def test_provider_module_rejects_unknown_provider(config: ConfigStore) -> None:
    """Provider module fails startup with a clear error on an unknown provider."""
    config.set("sync", "provider", "dropbox")
    with pytest.raises(ValueError, match="Unknown sync provider"):
        ProviderModule().create(config)
