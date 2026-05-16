from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import COLOUR_BTN_PRIMARY, COLOUR_BTN_SECONDARY, COLOUR_TEXT_PRIMARY
from piframe.widgets.base import Widget


class SegmentedControl(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        segments: list[str],
        selected: int = 0,
        assets=None,
        on_change: Callable[[int, str], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self._segments: list[str] = segments
        self._selected: int = max(0, min(len(segments) - 1, selected)) if segments else 0
        self._assets = assets
        self.on_change: Callable[[int, str], None] | None = on_change

    @property
    def selected(self) -> int:
        return self._selected

    def set_selected(self, i: int) -> None:
        if not self._segments:
            self._selected = 0
            return
        self._selected = max(0, min(len(self._segments) - 1, i))

    def draw(self, screen: pygame.Surface) -> None:
        if not self._segments:
            return
        seg_w = self.rect.width // len(self._segments)
        if self._assets is None:
            return
        font = self._assets.font(14)
        for i, label in enumerate(self._segments):
            seg_rect = pygame.Rect(self.rect.x + i * seg_w, self.rect.y, seg_w, self.rect.height)
            colour = COLOUR_BTN_PRIMARY[:3] if i == self._selected else COLOUR_BTN_SECONDARY[:3]
            pygame.draw.rect(screen, colour, seg_rect, border_radius=8)
            surf, _ = font.render(label, COLOUR_TEXT_PRIMARY[:3])
            text_rect = surf.get_rect(center=seg_rect.center)
            screen.blit(surf, text_rect.topleft)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and getattr(event, "button", 0) == 1
            and self.rect.collidepoint(event.pos)
            and self._segments
        ):
            seg_w = self.rect.width // len(self._segments)
            i = (event.pos[0] - self.rect.x) // seg_w if seg_w > 0 else 0
            i = max(0, min(len(self._segments) - 1, i))
            self._selected = i
            if self.on_change is not None:
                self.on_change(i, self._segments[i])
            return True
        return False
