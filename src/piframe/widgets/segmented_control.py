"""Segmented toggle control for mutually exclusive options."""
from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from piframe.assets import Assets

from piframe.types import COLOUR_BTN_PRIMARY, COLOUR_BTN_SECONDARY, COLOUR_TEXT_PRIMARY
from piframe.widgets.base import Widget


class SegmentedControl(Widget):
    """Segmented toggle control for mutually exclusive options."""

    def __init__(
        self,
        rect: pygame.Rect,
        segments: list[str],
        selected: int = 0,
        assets: Assets | None = None,
        on_change: Callable[[int, str], None] | None = None,
    ) -> None:
        """
        Create a segmented control.

        Args:
        rect: Position and size of the control.
        segments: List of segment labels.
        selected: Initial selected index.
        assets: Asset provider for fonts.
        on_change: Callback invoked when the selection changes.

        """
        super().__init__(rect)
        self._segments: list[str] = segments
        self._selected: int = max(0, min(len(segments) - 1, selected)) if segments else 0
        self._assets = assets
        self.on_change: Callable[[int, str], None] | None = on_change

    @property
    def selected(self) -> int:
        """The index of the currently selected segment."""
        return self._selected

    def set_selected(self, i: int) -> None:
        """Set the selected segment index."""
        if not self._segments:
            self._selected = 0
            return
        self._selected = max(0, min(len(self._segments) - 1, i))

    def draw(self, screen: pygame.Surface) -> None:
        """Render the segmented control with active segment highlighted."""
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
        """Handle tap events to select a segment."""
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
