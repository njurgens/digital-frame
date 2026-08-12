from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.sync_service import SyncService


class SyncModule(DimModule[SyncService]):
    def create(self, config: ConfigStore, **deps: object) -> SyncService:
        return SyncService(config)
