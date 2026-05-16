from __future__ import annotations

from enum import Enum

import pygame

from piframe.assets import (
    FONT_SIZE_BODY,
    FONT_SIZE_HEADING,
    IC_ARROW_BACK,
    Assets,
)
from piframe.config_store import ConfigStore
from piframe.types import (
    COLOUR_CONTENT_BG,
    COLOUR_DIVIDER,
    COLOUR_SIDEBAR_BG,
    COLOUR_TEXT_PRIMARY,
    COLOUR_TEXT_SECONDARY,
    SCREEN_H,
    SCREEN_W,
    SETTINGS_CONTENT_X,
    SIDEBAR_W,
)
from piframe.widgets.nav_item import NavItem
from piframe.widgets.segmented_control import SegmentedControl
from piframe.widgets.text_input import TextInput
from piframe.widgets.time_picker import TimePicker
from piframe.widgets.toggle import Toggle


class Section(Enum):
    SLIDESHOW = "Slideshow"
    DISPLAY = "Display"
    WIFI = "Wi-Fi"
    SYSTEM = "System"


class SettingsPanel:
    def __init__(self, assets: Assets, config: ConfigStore, on_brightness_change=None, on_focus_text=None):
        self._assets = assets
        self._config = config
        self._on_brightness_change = on_brightness_change
        self._on_focus_text = on_focus_text
        self._active_section = Section.SLIDESHOW
        self._visible = False
        self._build_nav()
        self._build_slideshow_widgets()
        self._build_display_widgets()
        self._build_wifi_widgets()
        self._system_widgets = []
        self._update_result = None

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
        content_x = SETTINGS_CONTENT_X + 18
        content_w = SCREEN_W - content_x - 18

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
        content_x = SETTINGS_CONTENT_X + 18
        content_w = SCREEN_W - content_x - 18

        brightness_options = [25, 50, 75, 100]
        labels = [f"{v}%" for v in brightness_options]
        try:
            brightness_selected = brightness_options.index(int(cfg.brightness))
        except ValueError:
            brightness_selected = min(range(len(brightness_options)), key=lambda i: abs(brightness_options[i] - int(cfg.brightness)))
        self._brightness_ctrl = SegmentedControl(
            rect=pygame.Rect(content_x, 80, content_w, 36),
            segments=labels,
            selected=brightness_selected,
            assets=self._assets,
            on_change=lambda i, _: self._set_brightness(brightness_options[i]),
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

        self._display_widgets = [
            self._brightness_ctrl,
            self._show_clock_toggle,
            self._sleep_enabled_toggle,
            self._sleep_time_picker,
            self._wake_time_picker,
        ]

    def _build_wifi_widgets(self):
        content_x = SETTINGS_CONTENT_X + 18
        content_w = SCREEN_W - content_x - 18
        self._wifi_password_input = TextInput(
            rect=pygame.Rect(content_x, 152, content_w, 44),
            placeholder="Wi-Fi password",
            password_mode=True,
            assets=self._assets,
            on_focus=lambda: self._on_focus_text(self._wifi_password_input) if self._on_focus_text else None,
        )
        self._wifi_widgets = [self._wifi_password_input]

    def _set_brightness(self, value: int) -> None:
        self._config.set("display", "brightness", value)
        if self._on_brightness_change is not None:
            self._on_brightness_change(value)

    def _select_section(self, section: Section):
        self._active_section = section
        for item in self._nav_items:
            item.active = item._label == section.value

    def open(self):
        self._visible = True

    def close(self):
        self._visible = False

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

    def _draw_display(self, screen: pygame.Surface):
        body_font = self._assets.font(FONT_SIZE_BODY)
        content_x = SETTINGS_CONTENT_X + 18
        rows = [
            ("Brightness", self._brightness_ctrl, 62),
            ("Show clock", self._show_clock_toggle, 144),
            ("Sleep schedule", self._sleep_enabled_toggle, 216),
        ]
        for label, widget, y_offset in rows:
            surf, _ = body_font.render(label, COLOUR_TEXT_SECONDARY[:3])
            screen.blit(surf, (content_x, y_offset))
            widget.draw(screen)

        tz_surf, _ = body_font.render(f"Timezone: {self._config.system.timezone}", COLOUR_TEXT_SECONDARY[:3])
        screen.blit(tz_surf, (content_x, 432))

        if self._sleep_enabled_toggle.value:
            sleep_surf, _ = body_font.render("Sleep time", COLOUR_TEXT_SECONDARY[:3])
            wake_surf, _ = body_font.render("Wake time", COLOUR_TEXT_SECONDARY[:3])
            screen.blit(sleep_surf, (content_x, 270))
            screen.blit(wake_surf, (content_x, 342))
            self._sleep_time_picker.draw(screen)
            self._wake_time_picker.draw(screen)

    def _draw_wifi(self, screen: pygame.Surface):
        body_font = self._assets.font(FONT_SIZE_BODY)
        content_x = SETTINGS_CONTENT_X + 18
        label_surf, _ = body_font.render("Wi-Fi password", COLOUR_TEXT_SECONDARY[:3])
        screen.blit(label_surf, (content_x, 124))
        self._wifi_password_input.draw(screen)

    def _active_widgets(self):
        if self._active_section == Section.SLIDESHOW:
            return self._slideshow_widgets
        if self._active_section == Section.DISPLAY:
            widgets = [self._brightness_ctrl, self._show_clock_toggle, self._sleep_enabled_toggle]
            if self._sleep_enabled_toggle.value:
                widgets.extend([self._sleep_time_picker, self._wake_time_picker])
            return widgets
        if self._active_section == Section.WIFI:
            return self._wifi_widgets
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

        for w in self._active_widgets():
            if w.handle_event(event):
                return True
        return False

    def on_wifi_result(self, result):
        pass

    def on_update_result(self, result):
        self._update_result = result

    def refresh_sync_status(self):
        pass
