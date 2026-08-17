# Dependency Injection — Module Pattern

> **Status:** Proposed
> **Date:** 2026-08-11
> **Issue:** #42 — Add dependency injection framework

## Goal

Replace manual conditional construction in `App.__init__()` with a **module pattern** — one class per service domain that encapsulates *which* implementation to construct based on config. No external DI library.

## Why no DI container?

The dependency graph is shallow (~8 services, max 2–3 levels deep). A container library (rodi, injector, etc.) adds a dependency and a mental model for marginal benefit over clean hand-wiring. The **module pattern** — protocol-based classes that encapsulate construction logic — is the real design win, and it works with or without a container.

## Design

### Module Protocol

```python
# piframe/di.py

from __future__ import annotations

from typing import Protocol, TypeVar, Generic, Any

from piframe.config_store import ConfigStore


T = TypeVar("T")


class DimModule(Protocol, Generic[T]):
    """A module that constructs a service from config and optional dependencies.

    Each service domain (wifi, cache, sync, etc.) implements this protocol.
    The `create` method encapsulates all conditional logic — config reads,
    environment checks, feature flags — so the caller never sees if/else.

    Design: see docs/dependency-injection.md
    """

    def create(self, config: ConfigStore, **deps: Any) -> T: ...
```

### Module Implementations

Each module lives in `piframe/modules/` and implements `DimModule[ReturnType]`.

#### WifiModule

```python
# piframe/modules/wifi.py

from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.types import WifiManagerProtocol
from piframe.wifi_manager import WifiManager
from piframe.app import MockWifiManager


class WifiModule(DimModule[WifiManagerProtocol]):
    """Constructs the appropriate WifiManager based on config.

    Config keys:
        app.mock_wifi (bool) — if true, use MockWifiManager.
    """

    def create(self, config: ConfigStore, **deps: object) -> WifiManagerProtocol:
        if config.app.mock_wifi:
            return MockWifiManager()
        return WifiManager()
```

#### CacheModule

```python
# piframe/modules/cache.py

from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.types import SCREEN_H, SCREEN_W


class CacheModule(DimModule[PhotoCache]):
    """Constructs PhotoCache with the default surface cache directory.

    The surface cache is a player implementation detail, not provider
    storage, so its location is not config-driven.
    """

    def create(self, config: ConfigStore, **deps: object) -> PhotoCache:
        return PhotoCache(screen_size=(SCREEN_W, SCREEN_H))
```

#### SyncModule

```python
# piframe/modules/sync.py

from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.providers import AlbumProvider
from piframe.sync_service import SyncService


class SyncModule(DimModule[SyncService]):
    """Constructs a SyncService that polls the given album provider."""

    def create(
        self, config: ConfigStore, *, provider: AlbumProvider, **deps: object
    ) -> SyncService:
        return SyncService(config, provider)
```

#### PlayerModule

```python
# piframe/modules/player.py

from __future__ import annotations

from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.photo_cache import PhotoCache
from piframe.providers import AlbumProvider
from piframe.slideshow_player import SlideshowPlayer
from piframe.types import SCREEN_H, SCREEN_W


class PlayerModule(DimModule[SlideshowPlayer]):
    """Constructs SlideshowPlayer with its dependencies."""

    def create(
        self,
        config: ConfigStore,
        *,
        provider: AlbumProvider,
        cache: PhotoCache,
        assets: Assets,
        **deps: object,
    ) -> SlideshowPlayer:
        return SlideshowPlayer(
            config=config,
            provider=provider,
            cache=cache,
            screen_size=(SCREEN_W, SCREEN_H),
            assets=assets,
        )
```

#### SettingsModule

```python
# piframe/modules/settings.py

from __future__ import annotations

from collections.abc import Callable

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.assets import Assets
from piframe.settings_panel import SettingsPanel
from piframe.sync_service import SyncService
from piframe.types import WifiManagerProtocol


class SettingsModule(DimModule[SettingsPanel]):
    """Constructs SettingsPanel with its dependencies."""

    def create(
        self,
        config: ConfigStore,
        *,
        assets: Assets,
        wifi_manager: WifiManagerProtocol,
        sync_service: SyncService,
        on_brightness_change: Callable[[int], None],
        on_focus_text: Callable,
        app_ref: object,
        **deps: object,
    ) -> SettingsPanel:
        return SettingsPanel(
            assets=assets,
            config=config,
            on_brightness_change=on_brightness_change,
            on_focus_text=on_focus_text,
            wifi_manager=wifi_manager,
            sync_service=sync_service,
            app_ref=app_ref,
        )
```

### App Startup

`App.__init__()` becomes a clean orchestration of module calls:

```python
class App:
    def __init__(self) -> None:
        self._args = self._parse_args()
        pygame.init()
        pygame.freetype.init()
        init_events()

        # ... screen setup ...

        self._assets = Assets.load()
        self._config = ConfigStore(config_path)

        # Modules construct services — conditional logic is encapsulated
        self._wifi = WifiModule().create(self._config)
        self._cache = CacheModule().create(self._config)
        self._sync = SyncModule().create(self._config)
        self._player = PlayerModule().create(self._config, cache=self._cache, assets=self._assets)
        self._settings = SettingsModule().create(
            self._config,
            assets=self._assets,
            wifi_manager=self._wifi,
            sync_service=self._sync,
            on_brightness_change=self._on_brightness_change,
            on_focus_text=self._on_focus_text,
            app_ref=self,
        )
        # ... remaining services ...
```

### Config Changes Required

Add an `[app]` section to `config.toml`:

```toml
[app]
mock_wifi = false        # use MockWifiManager instead of WifiManager
```

This replaces `--mock-wifi` CLI flag. The flag can remain as a shortcut that sets `config.app.mock_wifi = True` at load time, but the canonical source of truth is config.

## Adding a New Swappable Service

When a new service needs config-based swapping (e.g. the album provider), add a module that reads the selection from config and constructs the concrete implementation. The shipped example is `ProviderModule`, which reads `config.sync.provider` and builds the matching provider with its config wrapper:

```python
# piframe/modules/provider.py

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.providers import (
    AlbumProvider,
    GooglePhotosConfig,
    GooglePhotosProvider,
    LocalConfig,
    LocalProvider,
    OneDriveConfig,
    OneDriveProvider,
    ProviderName,
)


class ProviderModule(DimModule[AlbumProvider]):
    """Construct the album provider selected by ``config.sync.provider``."""

    def create(self, config: ConfigStore, **deps: object) -> AlbumProvider:
        name = config.sync.provider
        match name:
            case ProviderName.ONEDRIVE:
                return OneDriveProvider(OneDriveConfig(config))
            case ProviderName.LOCAL:
                return LocalProvider(LocalConfig(config))
            case ProviderName.GOOGLE:
                return GooglePhotosProvider(GooglePhotosConfig(config))
        raise ValueError(f"Unreachable provider name: {name!r}")
```

The module is registered in `App.__init__` before its consumers, and the DI container passes the constructed provider to the sync and player modules through their keyword dependencies:

```python
self._provider = ProviderModule().create(self._config)
```

No changes to other modules or the module protocol.

## Testing

For tests, bypass the module and construct directly:

```python
def test_slideshow_with_mock_wifi():
    config = ConfigStore(test_config_path)
    wifi = MockWifiManager()  # direct construction
    cache = PhotoCache(screen_size=(1280, 800))
    player = SlideshowPlayer(config, cache, (1280, 800))
    # ... assertions ...
```

Or override the config to drive the module:

```python
def test_wifi_module_selects_mock():
    config = ConfigStore(test_config_path)
    config.set("app", "mock_wifi", True)
    wifi = WifiModule().create(config)
    assert isinstance(wifi, MockWifiManager)
```

## Migration Plan

1. **Add `DimModule` protocol** to `piframe/di.py`.
2. **Add `[app]` section** to `config.toml` with `mock_wifi = false` default.
3. **Create module classes** for each service domain in `piframe/modules/`.
4. **Refactor `App.__init__()`** to use modules instead of inline construction.
5. **Remove `--mock-wifi` flag** (config drives the behavior).
6. **Update tests** to use direct construction or config-driven modules.

