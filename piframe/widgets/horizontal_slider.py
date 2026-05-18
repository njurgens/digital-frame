from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import COLOUR_SLIDER_FILL, COLOUR_SLIDER_THUMB, COLOUR_SLIDER_TRACK
from piframe.widgets.base import Widget


class HorizontalSlider(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        initial_value: int = 50,
        on_change: Callable[[int], None] | None = None,
    ):
        super().__init__(rect)
        self.value: int = max(0, min(100, initial_value))
        self._dragging: bool = False
        self.on_change: Callable[[int], None] | None = on_change

    def _value_to_x(self, value: int) -> int:
        return self.rect.left + 11 + int((value / 100) * (self.rect.width - 22))

    def _x_to_value(self, x: int) -> int:
        raw = (x - self.rect.left - 11) / (self.rect.width - 22)
        return round(max(0.0, min(1.0, raw)) * 100)

    def _apply_value(self, value: int) -> None:
        value = max(0, min(100, value))
        self.value = value
        self.dirty = True
        if self.on_change is not None:
            self.on_change(value)

    def set_value(self, value: int) -> None:
        self.value = max(0, min(100, value))
        self.dirty = True

    def draw(self, screen: pygame.Surface) -> None:
        rect = self.rect
        track_rect = pygame.Rect(rect.left, rect.centery - 2, rect.width, 4)
        pygame.draw.rect(screen, COLOUR_SLIDER_TRACK[:3], track_rect)

        thumb_x = self._value_to_x(self.value)
        fill_rect = pygame.Rect(track_rect.left, track_rect.top, thumb_x - rect.left, track_rect.height)
        pygame.draw.rect(screen, COLOUR_SLIDER_FILL[:3], fill_rect)
        pygame.draw.circle(screen, COLOUR_SLIDER_THUMB[:3], (thumb_x, rect.centery), 11)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
            hit_rect = self.rect.inflate(0, 20)
            x, y = event.pos
            if hit_rect.left <= x <= hit_rect.right and hit_rect.top <= y <= hit_rect.bottom:
                self._dragging = True
                self._apply_value(self._x_to_value(x))
                return True

        if event.type == pygame.MOUSEMOTION and self._dragging:
            self._apply_value(self._x_to_value(event.pos[0]))
            return True

        if event.type == pygame.MOUSEBUTTONUP and getattr(event, "button", 0) == 1:
            was_dragging = self._dragging
            self._dragging = False
            if was_dragging:
                return True

        return False
