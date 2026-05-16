from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import COLOUR_SCROLL_PICKER_HL
from piframe.widgets.base import Widget

VISIBLE_ROWS = 7
ROW_H = 44
WIDGET_H = 308


class ScrollPicker(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        items: list[str],
        selected: int = 0,
        assets=None,
        on_change: Callable[[int, str], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self._items: list[str] = items
        self._assets = assets
        self._surface_cache: dict[int, pygame.Surface] = {}
        self.on_change: Callable[[int, str], None] | None = on_change
        self._drag_y: int | None = None
        self._drag_offset: float = 0.0
        self._scroll_offset: float = 0.0
        self.set_selected(selected)

    def _clamp_offset(self, value: float) -> float:
        max_off = max(0.0, float(len(self._items) - VISIBLE_ROWS))
        return max(0.0, min(max_off, value))

    def _font(self):
        if self._assets is not None:
            return self._assets.font(18)
        return pygame.font.SysFont(None, 24)

    def _render_item(self, i: int) -> pygame.Surface:
        cached = self._surface_cache.get(i)
        if cached is not None:
            return cached
        font = self._font()
        rendered = font.render(self._items[i], (255, 255, 255))
        surf = rendered[0] if isinstance(rendered, tuple) else rendered
        self._surface_cache[i] = surf
        return surf

    def draw(self, screen: pygame.Surface) -> None:
        if not self._items:
            return
        rect = self.rect
        screen.set_clip(rect)
        hl_rect = pygame.Rect(rect.x, rect.y + ROW_H * 3, rect.width, ROW_H)
        hl = pygame.Surface((hl_rect.width, hl_rect.height), pygame.SRCALPHA)
        hl.fill(COLOUR_SCROLL_PICKER_HL)
        screen.blit(hl, hl_rect.topleft)

        first = int(self._scroll_offset)
        last = min(first + 8, len(self._items))
        for r in range(first, last):
            y_top = rect.top + (r - self._scroll_offset) * ROW_H
            if y_top + ROW_H < rect.top or y_top > rect.bottom:
                continue
            surf = self._render_item(r)
            y = int(y_top) + (ROW_H - surf.get_height()) // 2
            screen.blit(surf, (rect.x + 8, y))

        evict = [k for k in self._surface_cache if abs(k - first) > VISIBLE_ROWS * 3]
        for k in evict:
            del self._surface_cache[k]
        screen.set_clip(None)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1 and self.rect.collidepoint(event.pos):
            self._drag_y = event.pos[1]
            self._drag_offset = self._scroll_offset
            return True
        if event.type == pygame.MOUSEMOTION and self._drag_y is not None:
            self._scroll_offset = self._clamp_offset(self._drag_offset - (event.pos[1] - self._drag_y) / ROW_H)
            return True
        if event.type == pygame.MOUSEBUTTONUP and self._drag_y is not None and getattr(event, "button", 0) == 1:
            self._scroll_offset = self._clamp_offset(float(round(self._scroll_offset)))
            selected = max(0, min(len(self._items) - 1, int(self._scroll_offset + 3)))
            if self.on_change is not None and self._items:
                self.on_change(selected, self._items[selected])
            self._drag_y = None
            return True
        return False

    def get_selected(self) -> int:
        if not self._items:
            return 0
        return max(0, min(len(self._items) - 1, int(round(self._scroll_offset + 3))))

    def set_selected(self, i: int) -> None:
        if not self._items:
            self._scroll_offset = 0.0
            return
        i = max(0, min(len(self._items) - 1, i))
        self._scroll_offset = self._clamp_offset(max(0.0, i - 3.0))
