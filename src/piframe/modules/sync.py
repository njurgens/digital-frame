"""Sync module: constructs a SyncService from config."""
from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.sync_service import SyncService


class SyncModule(DimModule[SyncService]):
    """Construct a ``SyncService`` backed by the config store."""

    def create(self, config: ConfigStore, **deps: object) -> SyncService:
        """
        Build a sync service that polls framesync on an interval.

        Args:
            config: Application configuration.
            **deps: Unused.

        Returns:
            A ``SyncService`` instance.

        """
        return SyncService(config)
