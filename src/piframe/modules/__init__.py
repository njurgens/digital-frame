"""DI modules for constructing app services from config."""

from piframe.modules.cache import CacheModule
from piframe.modules.player import PlayerModule
from piframe.modules.settings import SettingsModule
from piframe.modules.sync import SyncModule
from piframe.modules.wifi import WifiModule

__all__ = [
    "CacheModule",
    "PlayerModule",
    "SettingsModule",
    "SyncModule",
    "WifiModule",
]
