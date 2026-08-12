from __future__ import annotations

from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.types import WifiManagerProtocol
from piframe.wifi_manager import MockWifiManager, WifiManager


class WifiModule(DimModule[WifiManagerProtocol]):
    """Construct a wifi manager, choosing real or mock based on config."""

    def create(self, config: ConfigStore, **deps: object) -> WifiManagerProtocol:
        """Return a ``WifiManager`` or ``MockWifiManager``.

        Args:
            config: Application configuration.
            **deps: Unused.

        Returns:
            A wifi manager implementing ``WifiManagerProtocol``.
        """
        if config.app.mock_wifi:
            return MockWifiManager()
        return WifiManager()
