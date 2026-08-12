"""Settings module: constructs a SettingsPanel with all required dependencies."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.di import DimModule
from piframe.settings_panel import SettingsPanel
from piframe.sync_service import SyncService
from piframe.types import WifiManagerProtocol

if TYPE_CHECKING:
    from piframe.app import App


class SettingsModule(DimModule[SettingsPanel]):
    """Construct a ``SettingsPanel`` with all required dependencies."""

    def create(
        self,
        config: ConfigStore,
        *,
        assets: Assets,
        wifi_manager: WifiManagerProtocol,
        sync_service: SyncService,
        on_brightness_change: Callable[[int], None],
        on_focus_text: Callable,
        app_ref: App,
        **deps: object,
    ) -> SettingsPanel:
        """
        Build a settings panel wired to the app's services.

        Args:
            config: Application configuration.
            assets: Asset provider for fonts and icons.
            wifi_manager: Wifi manager for network operations.
            sync_service: Sync service for photo sync status.
            on_brightness_change: Callback invoked when brightness changes.
            on_focus_text: Callback to show the keyboard for text input.
            app_ref: Reference to the owning ``App`` instance.
            **deps: Unused.

        Returns:
            A ``SettingsPanel`` instance.

        """
        return SettingsPanel(
            assets=assets,
            config=config,
            on_brightness_change=on_brightness_change,
            on_focus_text=on_focus_text,
            wifi_manager=wifi_manager,
            sync_service=sync_service,
            app_ref=app_ref,
        )
