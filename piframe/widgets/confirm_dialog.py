from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import (
    COLOUR_BTN_PRIMARY,
    COLOUR_BTN_SECONDARY,
    COLOUR_DESTRUCTIVE,
    COLOUR_DIALOG_BG,
    COLOUR_DIALOG_BORDER,
    COLOUR_SCRIM,
    COLOUR_TEXT_PRIMARY,
    COLOUR_TEXT_SECONDARY,
    SCREEN_H,
    SCREEN_W,
)
from piframe.widgets.base import Widget

DIALOG_W = 480
DIALOG_H = 240
DIALOG_X = 400
DIALOG_Y = 280


class ConfirmDialog(Widget):
    def __init__(
        self,
        title: str,
        body: str,
        confirm_label: str = "Confirm",
        destructive: bool = False,
        on_confirm: Callable[[], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
        assets=None,
    ) -> None:
        super().__init__(pygame.Rect(DIALOG_X, DIALOG_Y, DIALOG_W, DIALOG_H))
        self.title = title
        self.body = body
        self.confirm_label = confirm_label
        self.destructive = destructive
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self._assets = assets
        self._cancel_rect = pygame.Rect(DIALOG_X + 20, DIALOG_Y + 168, 196, 52)
        self._confirm_rect = pygame.Rect(DIALOG_X + 264, DIALOG_Y + 168, 196, 52)

    def draw(self, screen: pygame.Surface) -> None:
        scrim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        scrim.fill(COLOUR_SCRIM)
        screen.blit(scrim, (0, 0))

        dialog_rect = self.rect
        pygame.draw.rect(screen, COLOUR_DIALOG_BG[:3], dialog_rect, border_radius=12)
        pygame.draw.rect(screen, COLOUR_DIALOG_BORDER[:3], dialog_rect, 1, border_radius=12)

        if self._assets:
            font_title = self._assets.font_bold(24)
            font_body = self._assets.font(18)
            title_surf, _ = font_title.render(self.title, COLOUR_TEXT_PRIMARY[:3])
            screen.blit(title_surf, (dialog_rect.x + 24, dialog_rect.y + 30))
            body_surf, _ = font_body.render(self.body, COLOUR_TEXT_SECONDARY[:3])
            screen.blit(body_surf, (dialog_rect.x + 24, dialog_rect.y + 72))

            pygame.draw.rect(screen, COLOUR_BTN_SECONDARY[:3], self._cancel_rect, border_radius=8)
            cancel_surf, _ = font_body.render("Cancel", COLOUR_TEXT_PRIMARY[:3])
            screen.blit(
                cancel_surf,
                (
                    self._cancel_rect.centerx - cancel_surf.get_width() // 2,
                    self._cancel_rect.centery - cancel_surf.get_height() // 2,
                ),
            )

            confirm_bg = COLOUR_DESTRUCTIVE[:3] if self.destructive else COLOUR_BTN_PRIMARY[:3]
            pygame.draw.rect(screen, confirm_bg, self._confirm_rect, border_radius=8)
            confirm_surf, _ = font_body.render(self.confirm_label, COLOUR_TEXT_PRIMARY[:3])
            screen.blit(
                confirm_surf,
                (
                    self._confirm_rect.centerx - confirm_surf.get_width() // 2,
                    self._confirm_rect.centery - confirm_surf.get_height() // 2,
                ),
            )

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self._cancel_rect.collidepoint(event.pos):
                if self.on_cancel:
                    self.on_cancel()
                return True
            if self._confirm_rect.collidepoint(event.pos):
                if self.on_confirm:
                    self.on_confirm()
                return True
            if not self.rect.collidepoint(event.pos):
                if self.on_cancel:
                    self.on_cancel()
                return True
        return False
