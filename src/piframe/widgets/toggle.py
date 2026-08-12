"""Animated on/off toggle switch widget."""
from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import COLOUR_TOGGLE_OFF, COLOUR_TOGGLE_ON, COLOUR_TOGGLE_THUMB
from piframe.widgets.base import Widget


class Toggle(Widget):
    """Animated on/off toggle switch widget."""

    def __init__(
        self,
        rect: pygame.Rect,
        initial: bool = False,
        on_change: Callable[[bool], None] | None = None,
    ) -> None:
        """
        Create a toggle switch.

        Args:
        rect: Position and size of the toggle.
        initial: Initial on/off state.
        on_change: Callback invoked when the state changes.

        """
        super().__init__(rect)
        self._on: bool = initial
        self._anim_t: float = 1.0 if initial else 0.0
        self._speed: float = 1.0 / 0.12
        self.on_change: Callable[[bool], None] | None = on_change

    @property
    def value(self) -> bool:
        """The current on/off state of the toggle."""
        return self._on

    def set_value(self, v: bool) -> None:
        """Set the toggle value without triggering on_change."""
        self._on = v

    def update(self, dt: float) -> None:
        """Animate the thumb position toward the target state."""
        target = 1.0 if self._on else 0.0
        if self._anim_t != target:
            delta = self._speed * dt
            if self._on:
                self._anim_t = min(1.0, self._anim_t + delta)
            else:
                self._anim_t = max(0.0, self._anim_t - delta)

    def draw(self, screen: pygame.Surface) -> None:
        """Render the toggle track and animated thumb."""
        track_colour = tuple(
            int(COLOUR_TOGGLE_OFF[i] + (COLOUR_TOGGLE_ON[i] - COLOUR_TOGGLE_OFF[i]) * self._anim_t)
            for i in range(3)
        )
        pygame.draw.rect(screen, track_colour, self.rect, border_radius=14)
        thumb_x = self.rect.x + 14 + int(self._anim_t * 22)
        thumb_y = self.rect.centery
        pygame.draw.circle(screen, COLOUR_TOGGLE_THUMB[:3], (thumb_x, thumb_y), 11)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle tap events to toggle the state."""
        if (
            event.type == pygame.MOUSEBUTTONDOWN
            and getattr(event, "button", 0) == 1
            and self.rect.collidepoint(event.pos)
        ):
            self._on = not self._on
            if self.on_change is not None:
                self.on_change(self._on)
            return True
        return False
