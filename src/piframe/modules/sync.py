"""Sync module: constructs a SyncService from config and its provider."""

from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.providers import AlbumProvider
from piframe.sync_service import SyncService


class SyncModule(DimModule[SyncService]):
    """Construct a ``SyncService`` that polls the given album provider."""

    def create(
        self, config: ConfigStore, *, provider: AlbumProvider, **deps: object
    ) -> SyncService:
        """Build a sync service that delegates sync work to the provider.

        Args:
            config: Application configuration.
            provider: Album provider that owns the photos and sync status.
            **deps: Unused.

        Returns:
            A ``SyncService`` instance.

        """
        return SyncService(config, provider=provider)
