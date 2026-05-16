from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.assets import IC_VISIBILITY, IC_VISIBILITY_OFF
from piframe.types import COLOUR_BTN_PRIMARY, COLOUR_DIVIDER, COLOUR_TEXT_CAPTION, COLOUR_TEXT_PRIMARY
from piframe.widgets.base import Widget

_EYE_SIZE = 20  # icon size in px
_EYE_PADDING = 8  # gap from right edge


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
        self._show_text: bool = False  # toggle for password visibility
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

    def _eye_rect(self) -> pygame.Rect:
        """Hit-target for the show/hide password toggle icon."""
        rect = self.rect
        return pygame.Rect(
            rect.right - _EYE_SIZE - _EYE_PADDING,
            rect.centery - _EYE_SIZE // 2,
            _EYE_SIZE,
            _EYE_SIZE,
        )

    def _masked(self) -> bool:
        """True when text should be rendered as bullet characters."""
        return self._password_mode and not self._show_text

    def draw(self, screen: pygame.Surface) -> None:
        rect = self.rect
        border_colour = COLOUR_BTN_PRIMARY[:3] if self._focused else COLOUR_DIVIDER[:3]
        pygame.draw.rect(screen, border_colour, rect, 1, border_radius=4)

        if self._assets is None:
            return

        font = self._assets.font(18)

        # Reserve space for the eye icon when in password mode
        text_right = rect.right - (_EYE_SIZE + _EYE_PADDING * 2) if self._password_mode else rect.right - 8

        if not self._text:
            surf, _ = font.render(self._placeholder, COLOUR_TEXT_CAPTION[:3])
            screen.blit(surf, (rect.x + 8, rect.centery - surf.get_height() // 2))
        else:
            display = "●" * len(self._text) if self._masked() else self._text
            surf, _ = font.render(display, COLOUR_TEXT_PRIMARY[:3])
            # Clip text to available width
            clip = pygame.Rect(rect.x + 8, rect.y, text_right - rect.x - 8, rect.height)
            screen.set_clip(clip)
            screen.blit(surf, (rect.x + 8, rect.centery - surf.get_height() // 2))
            screen.set_clip(None)

        if self._focused:
            display_text = "●" * len(self._text) if self._masked() else self._text
            cursor_surf, _ = font.render(display_text, COLOUR_TEXT_PRIMARY[:3])
            cx = min(rect.x + 8 + cursor_surf.get_width() + 2, text_right)
            cy1 = rect.y + 6
            cy2 = rect.bottom - 6
            pygame.draw.line(screen, COLOUR_BTN_PRIMARY[:3], (cx, cy1), (cx, cy2), 2)

        if self._password_mode:
            icon = IC_VISIBILITY if self._show_text else IC_VISIBILITY_OFF
            icon_surf, icon_rect = self._assets.icon(_EYE_SIZE).render(icon, (160, 160, 160))
            eye = self._eye_rect()
            icon_rect.center = eye.center
            screen.blit(icon_surf, icon_rect)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
            pos = getattr(event, "pos", None)
            if pos is None:
                return False
            # Eye icon tap toggles password visibility
            if self._password_mode and self._eye_rect().collidepoint(pos):
                self._show_text = not self._show_text
                return True
            if self.rect.collidepoint(pos):
                self._focused = True
                if self.on_focus:
                    self.on_focus()
                return True
            self._focused = False
        return False
