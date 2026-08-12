from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.types import WifiManagerProtocol
from piframe.wifi_manager import MockWifiManager, WifiManager


class WifiModule(DimModule[WifiManagerProtocol]):
    def create(self, config: ConfigStore, **deps: object) -> WifiManagerProtocol:
        if config.app.mock_wifi:
            return MockWifiManager()
        return WifiManager()
