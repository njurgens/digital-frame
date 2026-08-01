from abc import ABC, abstractmethod

import pygame


class Widget(ABC):
    def __init__(self, rect: pygame.Rect):
        self.rect = rect
        self.dirty = True

    def set_rect(self, rect: pygame.Rect) -> None:
        self.rect = rect
        self.dirty = True

    @abstractmethod
    def draw(self, screen: pygame.Surface) -> None: ...

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> bool: ...

    def update(self, dt: float) -> None:
        pass
