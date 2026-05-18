from __future__ import annotations

import shutil
import socket
import threading
from enum import Enum
import zoneinfo

import pygame

from piframe.assets import (
    FONT_SIZE_BODY,
    FONT_SIZE_HEADING,
    IC_ARROW_BACK,
    Assets,
)
from piframe.config_store import ConfigStore
from piframe.updater import apply_update, check_update
from piframe.types import (
    COLOUR_BTN_PRIMARY,
    COLOUR_CONTENT_BG,
    COLOUR_DIVIDER,
    COLOUR_DESTRUCTIVE,
    COLOUR_SIDEBAR_BG,
    COLOUR_TEXT_PRIMARY,
    COLOUR_TEXT_SECONDARY,
    EVT_UPDATE_RESULT,
    UpdateResult,
    WifiStatus,
    SCREEN_H,
    SCREEN_W,
    SETTINGS_CONTENT_X,
    SIDEBAR_W,
)
from piframe.widgets.confirm_dialog import ConfirmDialog
from piframe.widgets.nav_item import NavItem
from piframe.widgets.scroll_picker import ScrollPicker
from piframe.widgets.segmented_control import SegmentedControl
from piframe.widgets.text_input import TextInput
from piframe.widgets.time_picker import TimePicker
from piframe.widgets.toggle import Toggle
from piframe.widgets.vertical_slider import VerticalSlider
from piframe.widgets.wifi_list_item import WifiListItem


class Section(Enum):
    SLIDESHOW = "Slideshow"
    DISPLAY = "Display"
    WIFI = "Wi-Fi"
    SYSTEM = "System"


CONTENT_X = SETTINGS_CONTENT_X + 18
CONTENT_W = SCREEN_W - CONTENT_X - 18
WIFI_LIST_Y = 200
WIFI_ITEM_H = 56
WIFI_MAX_ITEMS = 8


class SettingsPanel:
    def __init__(
        self,
        assets: Assets,
        config: ConfigStore,
        on_brightness_change=None,
        on_focus_text=None,
        wifi_manager=None,
        sync_service=None,
        app_ref=None,
    ):
        self._assets = assets
        self._config = config
        self._on_brightness_change = on_brightness_change
        self._on_focus_text = on_focus_text
        self._wifi_manager = wifi_manager
        self._sync_service = sync_service
        self._app_ref = app_ref
        self._active_section = Section.SLIDESHOW
        self._visible = False
        self._build_nav()
        self._build_slideshow_widgets()
        self._build_display_widgets()
        self._build_wifi_section()
        self._system_widgets = []
        self._update_result: UpdateResult | None = None
        self._system_message = ""
        self._sync_status = "Never synced"
        self._install_update_rect: pygame.Rect | None = None
        self._pending_dialog: ConfirmDialog | None = None
        self.refresh_sync_status()

    def _build_nav(self):
        from piframe.assets import IC_INFO, IC_SCHEDULE, IC_SETTINGS, IC_WIFI

        sections = [
            (Section.SLIDESHOW, "Slideshow", IC_SETTINGS),
            (Section.DISPLAY, "Display", IC_SCHEDULE),
            (Section.WIFI, "Wi-Fi", IC_WIFI),
            (Section.SYSTEM, "System", IC_INFO),
        ]
        self._nav_items = []
        for i, (section, label, icon) in enumerate(sections):
            y = 66 + i * 56
            rect = pygame.Rect(0, y, SIDEBAR_W, 56)
            item = NavItem(
                rect=rect,
                label=label,
                icon=icon,
                assets=self._assets,
                active=(section == self._active_section),
                on_select=lambda s=section: self._select_section(s),
            )
            self._nav_items.append(item)

    def _build_slideshow_widgets(self):
        cfg = self._config.slideshow
        content_x = CONTENT_X
        content_w = CONTENT_W

        interval_options = [("5s", 5), ("15s", 15), ("30s", 30), ("1m", 60), ("5m", 300)]
        interval_labels = [x[0] for x in interval_options]
        self._interval_values = [x[1] for x in interval_options]
        try:
            interval_selected = self._interval_values.index(int(cfg.interval))
        except ValueError:
            interval_selected = 2
        interval_rect = pygame.Rect(content_x, 80, content_w, 36)
        self._interval_ctrl = SegmentedControl(
            rect=interval_rect,
            segments=interval_labels,
            selected=interval_selected,
            assets=self._assets,
            on_change=lambda i, _: self._config.set("slideshow", "interval", float(self._interval_values[i])),
        )

        fit_options = ["Fit", "Fill"]
        fit_selected = 1 if cfg.fit_mode == "fill" else 0
        fit_rect = pygame.Rect(content_x, 152, content_w, 36)
        self._fit_ctrl = SegmentedControl(
            rect=fit_rect,
            segments=fit_options,
            selected=fit_selected,
            assets=self._assets,
            on_change=lambda i, _: self._config.set("slideshow", "fit_mode", "fill" if i == 1 else "fit"),
        )

        shuffle_rect = pygame.Rect(SCREEN_W - 68, 228, 50, 28)
        self._shuffle_toggle = Toggle(
            rect=shuffle_rect,
            initial=cfg.shuffle,
            on_change=lambda v: self._config.set("slideshow", "shuffle", v),
        )

        trans_options = ["Crossfade", "Cut", "Slide"]
        trans_map = {"crossfade": 0, "cut": 1, "slide": 2}
        trans_selected = trans_map.get(cfg.transition, 0)
        trans_rect = pygame.Rect(content_x, 300, content_w, 36)
        self._transition_ctrl = SegmentedControl(
            rect=trans_rect,
            segments=trans_options,
            selected=trans_selected,
            assets=self._assets,
            on_change=lambda i, lbl: self._config.set("slideshow", "transition", lbl.lower()),
        )

        self._slideshow_widgets = [
            self._interval_ctrl,
            self._fit_ctrl,
            self._shuffle_toggle,
            self._transition_ctrl,
        ]

    def _build_display_widgets(self):
        cfg = self._config.display
        sleep_cfg = self._config.sleep
        content_x = CONTENT_X
        content_w = CONTENT_W

        self._brightness_slider = VerticalSlider(
            rect=pygame.Rect(content_x + content_w - 64, 80, 40, 200),
            initial_value=cfg.brightness,
            on_change=self._on_brightness_change_display,
        )

        self._show_clock_toggle = Toggle(
            rect=pygame.Rect(SCREEN_W - 68, 162, 50, 28),
            initial=cfg.show_clock,
            on_change=lambda v: self._config.set("display", "show_clock", v),
        )
        self._sleep_enabled_toggle = Toggle(
            rect=pygame.Rect(SCREEN_W - 68, 234, 50, 28),
            initial=sleep_cfg.enabled,
            on_change=lambda v: self._config.set("sleep", "enabled", v),
        )

        sleep_hour, sleep_min = [int(x) for x in sleep_cfg.sleep_time.split(":")]
        wake_hour, wake_min = [int(x) for x in sleep_cfg.wake_time.split(":")]
        self._sleep_time_picker = TimePicker(
            rect=pygame.Rect(content_x, 288, 168, 44),
            initial_hour=sleep_hour,
            initial_minute=sleep_min,
            assets=self._assets,
            on_change=lambda h, m: self._config.set("sleep", "sleep_time", f"{h:02d}:{m:02d}"),
        )
        self._wake_time_picker = TimePicker(
            rect=pygame.Rect(content_x, 360, 168, 44),
            initial_hour=wake_hour,
            initial_minute=wake_min,
            assets=self._assets,
            on_change=lambda h, m: self._config.set("sleep", "wake_time", f"{h:02d}:{m:02d}"),
        )

        timezones = sorted(zoneinfo.available_timezones())
        current_tz = self._config.system.timezone
        current_idx = timezones.index(current_tz) if current_tz in timezones else 0
        self._tz_picker = ScrollPicker(
            rect=pygame.Rect(content_x, 400, content_w - 24, 308),
            items=timezones,
            selected=current_idx,
            assets=self._assets,
            on_change=lambda idx, tz: self._on_timezone_change(tz),
        )

        self._display_widgets = [
            self._brightness_slider,
            self._show_clock_toggle,
            self._sleep_enabled_toggle,
            self._sleep_time_picker,
            self._wake_time_picker,
            self._tz_picker,
        ]

    def _build_wifi_section(self):
        self._wifi_networks: list = []
        self._wifi_items: list[WifiListItem] = []
        self._wifi_status: WifiStatus | None = None
        self._wifi_connecting = False
        self._wifi_password_ssid: str | None = None
        self._wifi_password_input = TextInput(
            rect=pygame.Rect(CONTENT_X, 300, CONTENT_W - 24, 44),
            placeholder="Password",
            password_mode=True,
            assets=self._assets,
            on_focus=lambda: self._on_focus_text(self._wifi_password_input) if self._on_focus_text else None,
        )
        self._wifi_scan_rect = pygame.Rect(CONTENT_X, 136, 200, 44)
        self._wifi_forget_rect = pygame.Rect(CONTENT_X + 212, 136, 200, 44)
        self._wifi_connect_rect = pygame.Rect(CONTENT_X, 356, 200, 44)

    def _on_brightness_change_display(self, value: int) -> None:
        self._config.set("display", "brightness", value)
        if self._on_brightness_change is not None:
            self._on_brightness_change(value)

    def _on_timezone_change(self, tz: str) -> None:
        self._config.set("system", "timezone", tz)
        if self._app_ref is not None and hasattr(self._app_ref, "_clock_w"):
            self._app_ref._clock_w.set_timezone(tz)

    def _select_section(self, section: Section):
        self._active_section = section
        for item in self._nav_items:
            item.active = item._label == section.value
        if section == Section.WIFI and self._wifi_manager is not None:
            self._wifi_manager.get_status()
            self._wifi_manager.scan()

    def open(self):
        self._visible = True

    def close(self):
        self._visible = False

    def sync_from_config(self):
        """Re-sync all widget visual states from current config values.
        Call this after any programmatic config change so widgets stay in sync."""
        cfg = self._config.slideshow
        disp = self._config.display
        sleep = self._config.sleep
        try:
            self._interval_ctrl.set_selected(self._interval_values.index(int(cfg.interval)))
        except ValueError:
            pass
        self._fit_ctrl.set_selected(1 if cfg.fit_mode == "fill" else 0)
        try:
            trans_map = {"crossfade": 0, "cut": 1, "slide": 2}
            self._transition_ctrl.set_selected(trans_map.get(cfg.transition, 0))
        except Exception:
            pass
        self._shuffle_toggle.set_value(cfg.shuffle)
        self._show_clock_toggle.set_value(disp.show_clock)
        self._sleep_enabled_toggle.set_value(sleep.enabled)

    def update(self, dt: float):
        for w in self._active_widgets():
            w.update(dt)

    def draw(self, screen: pygame.Surface):
        if not self._visible:
            return
        pygame.draw.rect(screen, COLOUR_SIDEBAR_BG[:3], (0, 0, SIDEBAR_W, SCREEN_H))

        back_font = self._assets.font(FONT_SIZE_BODY)
        icon_font = self._assets.icon(24)
        icon_surf, _ = icon_font.render(IC_ARROW_BACK, COLOUR_TEXT_PRIMARY[:3])
        screen.blit(icon_surf, (8, 16))
        label_surf, _ = back_font.render("Back to frame", COLOUR_TEXT_PRIMARY[:3])
        screen.blit(label_surf, (36, 20))

        for item in self._nav_items:
            item.draw(screen)

        pygame.draw.rect(screen, COLOUR_CONTENT_BG[:3], (SIDEBAR_W, 0, SCREEN_W - SIDEBAR_W, SCREEN_H))
        title_font = self._assets.font_bold(FONT_SIZE_HEADING)
        title_surf, _ = title_font.render(self._active_section.value, COLOUR_TEXT_PRIMARY[:3])
        screen.blit(title_surf, (SETTINGS_CONTENT_X + 18, 18))
        pygame.draw.line(screen, COLOUR_DIVIDER[:3], (SETTINGS_CONTENT_X, 56), (SCREEN_W, 56))

        self._draw_section(screen)

    def _draw_section(self, screen: pygame.Surface):
        if self._active_section == Section.SLIDESHOW:
            self._draw_slideshow(screen)
        elif self._active_section == Section.DISPLAY:
            self._draw_display(screen)
        elif self._active_section == Section.WIFI:
            self._draw_wifi(screen)
        elif self._active_section == Section.SYSTEM:
            self._draw_system(screen)

    def _draw_slideshow(self, screen: pygame.Surface):
        body_font = self._assets.font(FONT_SIZE_BODY)
        content_x = SETTINGS_CONTENT_X + 18
        rows = [
            ("Interval", self._interval_ctrl, 62),
            ("Fit mode", self._fit_ctrl, 134),
            ("Shuffle", self._shuffle_toggle, 216),
            ("Transition", self._transition_ctrl, 282),
        ]
        for label, widget, y_offset in rows:
            surf, _ = body_font.render(label, COLOUR_TEXT_SECONDARY[:3])
            screen.blit(surf, (content_x, y_offset))
            widget.draw(screen)

        # Sync status row (belongs with slideshow content)
        self.refresh_sync_status()
        y = 340
        sync_label, _ = body_font.render("Sync status", COLOUR_TEXT_SECONDARY[:3])
        screen.blit(sync_label, (content_x, y))
        sync_value, _ = body_font.render(self._sync_status, COLOUR_TEXT_PRIMARY[:3])
        screen.blit(sync_value, (content_x + 150, y))

        y += 56
        sync_now_rect = pygame.Rect(content_x, y, 200, 44)
        self._draw_button(screen, sync_now_rect, "Sync now")
        self._sync_now_rect = sync_now_rect

    def _draw_display(self, screen: pygame.Surface):
        body_font = self._assets.font(FONT_SIZE_BODY)
        content_x = SETTINGS_CONTENT_X + 18
        rows = [
            ("Brightness", self._brightness_slider, 62),
            ("Show clock", self._show_clock_toggle, 144),
            ("Sleep schedule", self._sleep_enabled_toggle, 216),
        ]
        for label, widget, y_offset in rows:
            surf, _ = body_font.render(label, COLOUR_TEXT_SECONDARY[:3])
            screen.blit(surf, (content_x, y_offset))
            widget.draw(screen)

        tz_label, _ = body_font.render("Timezone", COLOUR_TEXT_SECONDARY[:3])
        screen.blit(tz_label, (content_x, 370))
        self._tz_picker.draw(screen)

        if self._sleep_enabled_toggle.value:
            sleep_surf, _ = body_font.render("Sleep time", COLOUR_TEXT_SECONDARY[:3])
            wake_surf, _ = body_font.render("Wake time", COLOUR_TEXT_SECONDARY[:3])
            screen.blit(sleep_surf, (content_x, 270))
            screen.blit(wake_surf, (content_x, 342))
            self._sleep_time_picker.draw(screen)
            self._wake_time_picker.draw(screen)

    def _draw_wifi(self, screen: pygame.Surface):
        body_font = self._assets.font(FONT_SIZE_BODY)
        caption_font = self._assets.font(14)
        content_x = CONTENT_X

        status_text = "Not connected"
        if self._wifi_status and self._wifi_status.connected:
            ip = f" ({self._wifi_status.ip_address})" if self._wifi_status.ip_address else ""
            status_text = f"{self._wifi_status.ssid}{ip}"
        status_surf, _ = body_font.render(status_text, COLOUR_TEXT_PRIMARY[:3])
        screen.blit(status_surf, (content_x, 80))

        pygame.draw.rect(screen, COLOUR_BTN_PRIMARY[:3], self._wifi_scan_rect, border_radius=6)
        scan_surf, _ = body_font.render("Scan for networks", COLOUR_TEXT_PRIMARY[:3])
        screen.blit(
            scan_surf,
            (
                self._wifi_scan_rect.centerx - scan_surf.get_width() // 2,
                self._wifi_scan_rect.centery - scan_surf.get_height() // 2,
            ),
        )

        if self._wifi_status and self._wifi_status.connected:
            pygame.draw.rect(screen, COLOUR_BTN_PRIMARY[:3], self._wifi_forget_rect, border_radius=6)
            forget_surf, _ = body_font.render("Forget current", COLOUR_TEXT_PRIMARY[:3])
            screen.blit(
                forget_surf,
                (
                    self._wifi_forget_rect.centerx - forget_surf.get_width() // 2,
                    self._wifi_forget_rect.centery - forget_surf.get_height() // 2,
                ),
            )

        for item in self._wifi_items:
            item.draw(screen)

        if self._wifi_password_ssid:
            prompt_surf, _ = caption_font.render(
                f"Password for {self._wifi_password_ssid}",
                COLOUR_TEXT_SECONDARY[:3],
            )
            screen.blit(prompt_surf, (content_x, 276))
            self._wifi_password_input.draw(screen)
            pygame.draw.rect(screen, COLOUR_BTN_PRIMARY[:3], self._wifi_connect_rect, border_radius=6)
            connect_surf, _ = body_font.render("Connect", COLOUR_TEXT_PRIMARY[:3])
            screen.blit(
                connect_surf,
                (
                    self._wifi_connect_rect.centerx - connect_surf.get_width() // 2,
                    self._wifi_connect_rect.centery - connect_surf.get_height() // 2,
                ),
            )

    def _draw_button(self, screen: pygame.Surface, rect: pygame.Rect, label: str, destructive: bool = False) -> None:
        body_font = self._assets.font(FONT_SIZE_BODY)
        bg = COLOUR_DESTRUCTIVE[:3] if destructive else COLOUR_BTN_PRIMARY[:3]
        pygame.draw.rect(screen, bg, rect, border_radius=6)
        surf, _ = body_font.render(label, COLOUR_TEXT_PRIMARY[:3])
        screen.blit(
            surf,
            (
                rect.centerx - surf.get_width() // 2,
                rect.centery - surf.get_height() // 2,
            ),
        )

    def _draw_system(self, screen: pygame.Surface) -> None:
        body_font = self._assets.font(FONT_SIZE_BODY)
        caption_font = self._assets.font(14)
        content_x = CONTENT_X
        y = 62

        # Device info rows
        for label, value in self._get_device_info():
            label_surf, _ = body_font.render(label, COLOUR_TEXT_SECONDARY[:3])
            value_surf, _ = body_font.render(value, COLOUR_TEXT_PRIMARY[:3])
            screen.blit(label_surf, (content_x, y))
            screen.blit(value_surf, (content_x + 150, y))
            y += 44

        y += 12  # extra gap before buttons

        # OTA check + restart buttons
        check_rect = pygame.Rect(content_x, y, 220, 44)
        restart_rect = pygame.Rect(content_x + 240, y, 180, 44)
        self._draw_button(screen, check_rect, "Check for update")
        self._draw_button(screen, restart_rect, "Restart app")
        self._check_update_rect = check_rect
        self._restart_rect = restart_rect

        y += 64
        if self._update_result is not None:
            if self._update_result.error:
                msg = f"Update check failed: {self._update_result.error}"
                colour = COLOUR_DESTRUCTIVE[:3]
            elif self._update_result.available:
                msg = f"Update available: {self._update_result.tag_name}"
                colour = COLOUR_TEXT_PRIMARY[:3]
            else:
                msg = "App is up to date"
                colour = COLOUR_TEXT_PRIMARY[:3]
            msg_surf, _ = body_font.render(msg, colour)
            screen.blit(msg_surf, (content_x, y))
            if self._update_result.available and self._update_result.tarball_url:
                install_rect = pygame.Rect(content_x + 360, y - 10, 140, 44)
                self._draw_button(screen, install_rect, "Install")
                self._install_update_rect = install_rect
            else:
                self._install_update_rect = None
        else:
            self._install_update_rect = None

        y += 72
        reboot_rect = pygame.Rect(content_x, y, 180, 44)
        shutdown_rect = pygame.Rect(content_x + 200, y, 180, 44)
        self._draw_button(screen, reboot_rect, "Reboot")
        self._draw_button(screen, shutdown_rect, "Shutdown", destructive=True)
        self._reboot_rect = reboot_rect
        self._shutdown_rect = shutdown_rect

        if self._system_message:
            info_surf, _ = caption_font.render(self._system_message, COLOUR_TEXT_SECONDARY[:3])
            screen.blit(info_surf, (content_x, y + 64))

    def _get_device_info(self) -> list[tuple[str, str]]:
        """Return [(label, value)] rows for the System section device info block."""
        rows = []

        # App version from git tag; falls back to a hardcoded constant
        try:
            import subprocess
            tag = subprocess.check_output(
                ["git", "-C", "/home/frame/digital-frame", "describe", "--tags", "--abbrev=0"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode().strip()
        except Exception:
            tag = getattr(self, "_APP_VERSION", "dev")
        rows.append(("Version", tag))

        # IP address via UDP connect trick (no packets sent)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "unknown"
        rows.append(("IP address", ip))

        # Uptime from /proc/uptime
        try:
            with open("/proc/uptime") as f:
                secs = float(f.read().split()[0])
            days, rem = divmod(int(secs), 86400)
            hours, rem = divmod(rem, 3600)
            mins = rem // 60
            if days:
                uptime = f"{days}d {hours}h {mins}m"
            else:
                uptime = f"{hours}h {mins}m"
        except Exception:
            uptime = "unknown"
        rows.append(("Uptime", uptime))

        # Storage usage for the photos directory
        try:
            photos_dir = self._config.sync.output_dir if self._config else "/home/frame/Pictures/slideshow"
            usage = shutil.disk_usage(photos_dir)
            used_gb = usage.used / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            storage = f"{used_gb:.1f} / {total_gb:.0f} GB"
        except Exception:
            storage = "unknown"
        rows.append(("Storage", storage))

        return rows

    def _active_widgets(self):
        if self._active_section == Section.SLIDESHOW:
            return self._slideshow_widgets
        if self._active_section == Section.DISPLAY:
            widgets = [
                self._brightness_slider,
                self._show_clock_toggle,
                self._sleep_enabled_toggle,
                self._tz_picker,
            ]
            if self._sleep_enabled_toggle.value:
                widgets.extend([self._sleep_time_picker, self._wake_time_picker])
            return widgets
        if self._active_section == Section.WIFI:
            widgets = []
            if self._wifi_password_ssid:
                widgets.append(self._wifi_password_input)
            return widgets
        if self._active_section == Section.SYSTEM:
            return self._system_widgets
        return []

    def on_tap(self, event_or_pos) -> bool:
        if isinstance(event_or_pos, tuple):
            event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=event_or_pos, button=1)
        else:
            event = event_or_pos
        pos = getattr(event, "pos", None)
        if pos is None:
            return False

        if pygame.Rect(0, 0, SIDEBAR_W, 58).collidepoint(pos):
            return False

        for item in self._nav_items:
            if item.handle_event(event):
                return True

        if self._active_section == Section.WIFI and event.type == pygame.MOUSEBUTTONDOWN:
            if self._wifi_scan_rect.collidepoint(pos):
                self._wifi_connecting = True
                if self._wifi_manager is not None:
                    self._wifi_manager.scan()
                return True
            if (
                self._wifi_forget_rect.collidepoint(pos)
                and self._wifi_status is not None
                and self._wifi_status.connected
            ):
                self._on_forget_tap()
                return True
            if self._wifi_password_ssid and self._wifi_connect_rect.collidepoint(pos):
                self._wifi_connecting = True
                if self._wifi_manager is not None:
                    password = self._wifi_password_input.text or None
                    self._wifi_manager.connect(self._wifi_password_ssid, password)
                return True

        if self._active_section == Section.WIFI:
            for item in self._wifi_items:
                if item.handle_event(event):
                    return True

        if self._active_section == Section.SLIDESHOW and event.type == pygame.MOUSEBUTTONDOWN:
            if hasattr(self, "_sync_now_rect") and self._sync_now_rect.collidepoint(pos):
                if self._sync_service is not None:
                    self._sync_service.trigger()
                    self._system_message = "Sync triggered"
                else:
                    self._system_message = "Sync service unavailable"
                return True

        if self._active_section == Section.SYSTEM and event.type == pygame.MOUSEBUTTONDOWN:
            if hasattr(self, "_check_update_rect") and self._check_update_rect.collidepoint(pos):
                self._check_update_async()
                return True
            if self._install_update_rect and self._install_update_rect.collidepoint(pos) and self._update_result is not None:
                self._apply_update_async(self._update_result.tarball_url)
                return True
            if hasattr(self, "_restart_rect") and self._restart_rect.collidepoint(pos):
                if self._app_ref is not None:
                    self._app_ref.restart()
                return True
            if hasattr(self, "_reboot_rect") and self._reboot_rect.collidepoint(pos):
                self._show_reboot_confirm()
                return True
            if hasattr(self, "_shutdown_rect") and self._shutdown_rect.collidepoint(pos):
                self._show_shutdown_confirm()
                return True

        for w in self._active_widgets():
            if w.handle_event(event):
                return True
        return False

    def on_wifi_result(self, result):
        if result.operation == "scan":
            if result.success:
                self._wifi_networks = result.data or []
                self._rebuild_wifi_items()
            self._wifi_connecting = False
        elif result.operation == "connect":
            self._wifi_connecting = False
            self._wifi_password_ssid = None
            self._rebuild_wifi_items()
            if result.success and self._wifi_manager is not None:
                self._wifi_manager.get_status()
        elif result.operation == "status":
            if result.success:
                self._wifi_status = result.data
                self._rebuild_wifi_items()
        elif result.operation == "forget":
            if result.success and self._wifi_manager is not None:
                self._wifi_manager.get_status()

    def _rebuild_wifi_items(self) -> None:
        current_ssid = self._wifi_status.ssid if self._wifi_status and self._wifi_status.connected else ""
        self._wifi_items = []
        max_items = WIFI_MAX_ITEMS
        if self._wifi_password_ssid:
            available_h = max(0, self._wifi_password_input.rect.top - WIFI_LIST_Y)
            max_items = min(max_items, available_h // WIFI_ITEM_H)
        y = WIFI_LIST_Y
        for net in self._wifi_networks[:max_items]:
            item = WifiListItem(
                rect=pygame.Rect(CONTENT_X, y, CONTENT_W - 24, 56),
                network=net,
                current_ssid=current_ssid,
                assets=self._assets,
                on_tap=self._on_wifi_network_tap,
            )
            self._wifi_items.append(item)
            y += WIFI_ITEM_H

    def _on_wifi_network_tap(self, network) -> None:
        if network.security and network.security != "--":
            self._wifi_password_ssid = network.ssid
            self._wifi_password_input.clear()
            self._rebuild_wifi_items()
            return
        if self._wifi_manager is not None:
            self._wifi_connecting = True
            self._wifi_manager.connect(network.ssid, None)

    def _on_forget_tap(self) -> None:
        if not self._wifi_status or not self._wifi_status.ssid:
            return
        ssid = self._wifi_status.ssid

        def _confirm() -> None:
            if self._app_ref is not None:
                self._app_ref._dialog = None
            if self._wifi_manager is not None:
                self._wifi_connecting = True
                self._wifi_manager.forget(ssid)

        def _cancel() -> None:
            if self._app_ref is not None:
                self._app_ref._dialog = None

        self._pending_dialog = ConfirmDialog(
            title="Forget Network?",
            body=f'Remove "{ssid}" from saved networks?',
            confirm_label="Forget",
            destructive=True,
            on_confirm=_confirm,
            on_cancel=_cancel,
            assets=self._assets,
        )
        if self._app_ref is not None:
            self._app_ref._dialog = self._pending_dialog

    def on_update_result(self, result: UpdateResult) -> None:
        self._update_result = result
        if result.error:
            self._system_message = f"Update check failed: {result.error}"
        elif result.available:
            self._system_message = f"Update available: {result.tag_name}"
        else:
            self._system_message = "No updates available"

    def refresh_sync_status(self) -> None:
        if self._sync_service is None:
            self._sync_status = "Never synced"
            return
        status = self._sync_service.status
        if status.in_progress:
            self._sync_status = "Sync in progress..."
            return
        if status.last_error:
            ts = status.last_sync_time.strftime("%H:%M:%S") if status.last_sync_time else "?"
            self._sync_status = f"Sync error at {ts}: {status.last_error}"
            return
        if status.last_sync_time is None:
            self._sync_status = "Never synced"
            return
        last_sync = status.last_sync_time.strftime("%Y-%m-%d %H:%M")
        self._sync_status = f"Last sync: {last_sync} ({status.photo_count} photos)"

    def _check_update_async(self) -> None:
        repo = self._config.update.repo
        self._system_message = "Checking for updates..."

        def _worker() -> None:
            try:
                tag_name, tarball_url = check_update(repo)
                result = UpdateResult(available=bool(tarball_url), tag_name=tag_name, tarball_url=tarball_url)
            except Exception as exc:
                result = UpdateResult(available=False, error=str(exc))
            if EVT_UPDATE_RESULT is not None:
                try:
                    pygame.event.post(pygame.event.Event(EVT_UPDATE_RESULT, result=result))
                except pygame.error:
                    self.on_update_result(result)
            else:
                self.on_update_result(result)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_update_async(self, tarball_url: str) -> None:
        self._system_message = "Installing update..."

        def _worker() -> None:
            try:
                apply_update(tarball_url)
                self._system_message = "Update installed. Restarting..."
                if self._app_ref is not None:
                    self._app_ref.restart()
            except Exception as exc:
                self._system_message = f"Update failed: {exc}"

        threading.Thread(target=_worker, daemon=True).start()

    def _set_dialog(self, dialog: ConfirmDialog) -> None:
        if self._app_ref is not None:
            self._app_ref._dialog = dialog

    def _show_reboot_confirm(self) -> None:
        if self._app_ref is None:
            return

        def _confirm() -> None:
            self._app_ref._dialog = None
            self._app_ref._reboot()

        def _cancel() -> None:
            self._app_ref._dialog = None

        self._set_dialog(
            ConfirmDialog(
                title="Reboot?",
                body="Restart the frame now.",
                confirm_label="Reboot",
                on_confirm=_confirm,
                on_cancel=_cancel,
                assets=self._assets,
            )
        )

    def _show_shutdown_confirm(self) -> None:
        if self._app_ref is None:
            return

        def _confirm() -> None:
            self._app_ref._dialog = None
            self._app_ref._shutdown()

        def _cancel() -> None:
            self._app_ref._dialog = None

        self._set_dialog(
            ConfirmDialog(
                title="Shutdown?",
                body="Power off the frame now.",
                confirm_label="Shutdown",
                destructive=True,
                on_confirm=_confirm,
                on_cancel=_cancel,
                assets=self._assets,
            )
        )
