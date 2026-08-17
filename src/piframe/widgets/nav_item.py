"""Sidebar navigation item widget."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from piframe.assets import Assets

from piframe.types import (
    COLOUR_CONNECTED,
    COLOUR_NAV_ACTIVE_BG,
    COLOUR_TEXT_PRIMARY,
    COLOUR_TEXT_SECONDARY,
)
from piframe.widgets.base import Widget


class NavItem(Widget):
    """Sidebar navigation item with icon, label, and active state."""

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        icon: str,
        assets: Assets,
        active: bool = False,
        on_select: Callable[[], None] | None = None,
    ) -> None:
        """Create a navigation item.

        Args:
        rect: Position and size of the item.
        label: Display text for the item.
        icon: Material Icons character for the item.
        assets: Asset provider for fonts and icons.
        active: Whether the item is currently selected.
        on_select: Callback invoked when the item is tapped.

        """
        super().__init__(rect)
        self._label = label
        self._icon = icon
        self._assets = assets
        self._active = active
        self.on_select: Callable[[], None] | None = on_select

    @property
    def active(self) -> bool:
        """Whether the nav item is currently selected."""
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value

    def draw(self, screen: pygame.Surface) -> None:
        """Render the nav item with icon and label."""
        if self._active:
            bg = pygame.Surface((self.rect.width, 56), pygame.SRCALPHA)
            bg.fill(COLOUR_NAV_ACTIVE_BG)
            screen.blit(bg, self.rect.topleft)

        icon_colour = COLOUR_CONNECTED[:3] if self._active else COLOUR_TEXT_SECONDARY[:3]
        text_colour = COLOUR_TEXT_PRIMARY[:3] if self._active else COLOUR_TEXT_SECONDARY[:3]

        icon_font = self._assets.icon(24)
        icon_surf, _ = icon_font.render(self._icon, icon_colour)
        icon_rect = icon_surf.get_rect(center=(self.rect.x + 28, self.rect.centery))
        screen.blit(icon_surf, icon_rect.topleft)

        label_font = self._assets.font(20)
        label_surf, _ = label_font.render(self._label, text_colour)
        font_height = label_font.get_sized_height()  # type: ignore[call-arg]
        screen.blit(label_surf, (self.rect.x + 56, self.rect.centery - font_height // 2))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle tap events to select the nav item."""
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and getattr(event, "button", 0) == 1
            and self.rect.collidepoint(event.pos)
        ):
            self.active = True
            if self.on_select is not None:
                self.on_select()
            return True
        return False
