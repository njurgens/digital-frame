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
from piframe.widgets.toggle import Toggle


class Section(Enum):
    SLIDESHOW = "Slideshow"
    DISPLAY = "Display"
    WIFI = "Wi-Fi"
    SYSTEM = "System"


class SettingsPanel:
    def __init__(self, assets: Assets, config: ConfigStore):
        self._assets = assets
        self._config = config
        self._active_section = Section.SLIDESHOW
        self._visible = False
        self._build_nav()
        self._build_slideshow_widgets()
        self._display_widgets = []
        self._wifi_widgets = []
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

    def _active_widgets(self):
        if self._active_section == Section.SLIDESHOW:
            return self._slideshow_widgets
        return []

    def on_tap(self, pos: tuple[int, int]) -> bool:
        if pygame.Rect(0, 0, SIDEBAR_W, 58).collidepoint(pos):
            return False

        for item in self._nav_items:
            if item.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)):
                return True

        for w in self._active_widgets():
            if w.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)):
                return True
        return False

    def on_wifi_result(self, result):
        pass

    def on_update_result(self, result):
        self._update_result = result

    def refresh_sync_status(self):
        pass
