from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import COLOUR_BTN_PRIMARY, COLOUR_DIVIDER, COLOUR_TEXT_CAPTION, COLOUR_TEXT_PRIMARY
from piframe.widgets.base import Widget


class TextInput(Widget):
    def __init__(
        self,
        rect: pygame.Rect,
        placeholder: str = "",
        password_mode: bool = False,
        assets=None,
        on_focus: Callable[[], None] | None = None,
        on_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(rect)
        self._text: str = ""
        self._placeholder: str = placeholder
        self._focused: bool = False
        self._password_mode: bool = password_mode
        self._assets = assets
        self.on_focus: Callable[[], None] | None = on_focus
        self.on_change: Callable[[str], None] | None = on_change

    @property
    def text(self) -> str:
        return self._text

    def clear(self) -> None:
        self._text = ""
        if self.on_change:
            self.on_change(self._text)

    def append(self, ch: str) -> None:
        self._text += ch
        if self.on_change:
            self.on_change(self._text)

    def backspace(self) -> None:
        self._text = self._text[:-1]
        if self.on_change:
            self.on_change(self._text)

    def set_focused(self, focused: bool) -> None:
        self._focused = focused

    def draw(self, screen: pygame.Surface) -> None:
        rect = self.rect
        border_colour = COLOUR_BTN_PRIMARY[:3] if self._focused else COLOUR_DIVIDER[:3]
        pygame.draw.rect(screen, border_colour, rect, 1, border_radius=4)

        if self._assets is None:
            return

        font = self._assets.font(18)
        if not self._text:
            surf, _ = font.render(self._placeholder, COLOUR_TEXT_CAPTION[:3])
            screen.blit(surf, (rect.x + 8, rect.centery - surf.get_height() // 2))
        else:
            display = "●" * len(self._text) if self._password_mode else self._text
            surf, _ = font.render(display, COLOUR_TEXT_PRIMARY[:3])
            screen.blit(surf, (rect.x + 8, rect.centery - surf.get_height() // 2))

        if self._focused:
            display_text = "●" * len(self._text) if self._password_mode else self._text
            cursor_surf, _ = font.render(display_text, COLOUR_TEXT_PRIMARY[:3])
            cx = rect.x + 8 + cursor_surf.get_width() + 2
            cy1 = rect.y + 6
            cy2 = rect.bottom - 6
            pygame.draw.line(screen, COLOUR_BTN_PRIMARY[:3], (cx, cy1), (cx, cy2), 2)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
            if self.rect.collidepoint(event.pos):
                self._focused = True
                if self.on_focus:
                    self.on_focus()
                return True
            self._focused = False
        return False
