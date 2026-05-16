from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import (
    COLOUR_DIALOG_BG,
    COLOUR_DIALOG_BORDER,
    COLOUR_PILL_BG,
    COLOUR_PILL_BORDER,
    COLOUR_TEXT_PRIMARY,
    SCREEN_H,
    SCREEN_W,
)
from piframe.widgets.base import Widget
from piframe.widgets.scroll_picker import ScrollPicker


class TimePicker(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        initial_hour: int = 22,
        initial_minute: int = 0,
        assets=None,
        on_change: Callable[[int, int], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self._assets = assets
        self._hour: int = max(0, min(23, initial_hour))
        self._minute: int = max(0, min(59, initial_minute))
        self._popup_open: bool = False
        self.on_change: Callable[[int, int], None] | None = on_change

        popup_y = rect.bottom + 4
        if popup_y + 280 > SCREEN_H:
            popup_y = rect.top - 280 - 4
        popup_x = max(0, min(rect.centerx - 160, SCREEN_W - 320))
        self._popup_rect = pygame.Rect(popup_x, popup_y, 320, 280)

        picker_top = self._popup_rect.y + 44
        picker_h = self._popup_rect.height - 52
        self._hour_picker = ScrollPicker(
            pygame.Rect(self._popup_rect.x + 12, picker_top, 140, picker_h),
            [f"{h:02d}" for h in range(24)],
            selected=self._hour,
            assets=assets,
        )
        self._min_picker = ScrollPicker(
            pygame.Rect(self._popup_rect.x + 168, picker_top, 140, picker_h),
            [f"{m:02d}" for m in range(60)],
            selected=self._minute,
            assets=assets,
        )

    def _draw_pill(self, screen: pygame.Surface, rect: pygame.Rect, text: str) -> None:
        pygame.draw.rect(screen, COLOUR_PILL_BG[:3], rect, border_radius=22)
        pygame.draw.rect(screen, COLOUR_PILL_BORDER[:3], rect, width=1, border_radius=22)
        if self._assets is None:
            return
        surf, _ = self._assets.font(18).render(text, COLOUR_TEXT_PRIMARY[:3])
        screen.blit(surf, surf.get_rect(center=rect.center).topleft)

    def draw(self, screen: pygame.Surface) -> None:
        hour_rect = pygame.Rect(self.rect.x, self.rect.y, 80, 44)
        min_rect = pygame.Rect(self.rect.x + 88, self.rect.y, 80, 44)
        self._draw_pill(screen, hour_rect, f"{self._hour:02d}")
        self._draw_pill(screen, min_rect, f"{self._minute:02d}")

        if not self._popup_open:
            return
        pygame.draw.rect(screen, COLOUR_DIALOG_BG[:3], self._popup_rect, border_radius=8)
        pygame.draw.rect(screen, COLOUR_DIALOG_BORDER[:3], self._popup_rect, width=1, border_radius=8)
        self._hour_picker.draw(screen)
        self._min_picker.draw(screen)
        done_rect = pygame.Rect(self._popup_rect.right - 40, self._popup_rect.y + 8, 32, 32)
        pygame.draw.rect(screen, COLOUR_PILL_BG[:3], done_rect, border_radius=16)
        pygame.draw.rect(screen, COLOUR_PILL_BORDER[:3], done_rect, width=1, border_radius=16)
        if self._assets is not None:
            surf, _ = self._assets.font_bold(18).render("✓", COLOUR_TEXT_PRIMARY[:3])
            screen.blit(surf, surf.get_rect(center=done_rect.center).topleft)

    def handle_event(self, event: pygame.event.Event) -> bool:
        hour_rect = pygame.Rect(self.rect.x, self.rect.y, 80, 44)
        min_rect = pygame.Rect(self.rect.x + 88, self.rect.y, 80, 44)
        done_rect = pygame.Rect(self._popup_rect.right - 40, self._popup_rect.y + 8, 32, 32)

        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
            if hour_rect.collidepoint(event.pos) or min_rect.collidepoint(event.pos):
                self._popup_open = True
                self._hour_picker.set_selected(self._hour)
                self._min_picker.set_selected(self._minute)
                return True
            if self._popup_open and done_rect.collidepoint(event.pos):
                self._hour = self._hour_picker.get_selected()
                self._minute = self._min_picker.get_selected()
                if self.on_change is not None:
                    self.on_change(self._hour, self._minute)
                self._popup_open = False
                return True
            if self._popup_open and not self._popup_rect.collidepoint(event.pos):
                self._popup_open = False
                return True

        if self._popup_open and self._hour_picker.handle_event(event):
            return True
        if self._popup_open and self._min_picker.handle_event(event):
            return True
        return False
