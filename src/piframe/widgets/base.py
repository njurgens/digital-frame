"""Abstract base class for all UI widgets."""
from abc import ABC, abstractmethod

import pygame


class Widget(ABC):
    """Abstract base class for all UI widgets."""

    def __init__(self, rect: pygame.Rect):
        """
        Create a widget at the given rect.

        Args:
        rect: Position and size of the widget.

        """
        self.rect = rect
        self.dirty = True

    def set_rect(self, rect: pygame.Rect) -> None:
        """Update the widget position and size."""
        self.rect = rect
        self.dirty = True

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None:
        """Render the widget onto the screen."""
        ...

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle a pygame event and return whether it was consumed."""
        ...

    def update(self, dt: float) -> None:
        """Update the widget state by the given time delta."""
        pass
