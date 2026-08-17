"""Provider module: constructs the album provider selected by config."""

from __future__ import annotations

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
    """Construct the album provider selected by ``config.sync.provider``.

    The provider set is small and stable, so selection is an inline
    conditional rather than a registry (D-8).  An unknown provider value
    raises from ``config.sync.provider`` with a clear message, failing
    startup instead of silently falling back (FR-6).
    """

    def create(self, config: ConfigStore, **deps: object) -> AlbumProvider:
        """Build the provider named in the sync config section.

        Args:
            config: Application configuration.
            **deps: Unused.

        Returns:
            The selected ``AlbumProvider`` instance.

        """
        name = config.sync.provider
        match name:
            case ProviderName.ONEDRIVE:
                return OneDriveProvider(OneDriveConfig(config))
            case ProviderName.LOCAL:
                return LocalProvider(LocalConfig(config))
            case ProviderName.GOOGLE:
                return GooglePhotosProvider(GooglePhotosConfig(config))
        raise ValueError(f"Unreachable provider name: {name!r}")
