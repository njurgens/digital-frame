from __future__ import annotations

from collections.abc import Callable

import pygame

from piframe.types import (
    COLOUR_KEY_BG,
    COLOUR_KEY_BG_ACTIVE,
    COLOUR_KEY_BG_SPECIAL,
    COLOUR_SIDEBAR_BG,
    COLOUR_TEXT_PRIMARY,
    SCREEN_W,
)

ALPHA = [
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    ["SHIFT"] + list("ZXCVBNM") + ["BACKSPACE"],
    ["123", "SPACE", "DONE"],
]
NUMERIC = [
    list("1234567890"),
    list("-/:;()$&@"),
    ["#+="] + list(".,?!'") + ["BACKSPACE"],
    ["ABC", "SPACE", "DONE"],
]
EXTENDED = [
    list("[]{}#%^*+="),
    list(r"_\|~<>€£¥"),
    ["123"] + list(".,?!'") + ["BACKSPACE"],
    ["ABC", "SPACE", "DONE"],
]
LAYERS = {"alpha": ALPHA, "numeric": NUMERIC, "extended": EXTENDED}

KB_Y = 450
KB_H = 350
ROW_H = 75
IC_SHIFT = "\ue5d8"
IC_SHIFT_LOCK = "\ue318"
IC_BACKSPACE = "\ue14a"


class Keyboard:
    def __init__(self, assets, on_done: Callable[[], None] | None = None):
        self._assets = assets
        self._layer: str = "alpha"
        self._shift: bool = False
        self._target = None
        self._visible: bool = False
        self._active_key: tuple[int, int] | None = None
        self._on_done: Callable[[], None] | None = on_done
        self._key_rects: list[list[pygame.Rect]] = []
        self._build_rects()

    def _build_rects(self) -> None:
        layer_keys = LAYERS[self._layer]
        self._key_rects = []
        row_y_tops = [462, 545, 628, 711]
        for r, (row, row_y) in enumerate(zip(layer_keys, row_y_tops)):
            row_rects: list[pygame.Rect] = []
            if r == 0:
                x = 12
                for _key in row:
                    row_rects.append(pygame.Rect(x, row_y, 122, ROW_H))
                    x += 126
            elif r == 1:
                x = 75
                for _key in row:
                    row_rects.append(pygame.Rect(x, row_y, 122, ROW_H))
                    x += 126
            elif r == 2:
                row_rects.append(pygame.Rect(41, row_y, 156, ROW_H))
                x = 201
                for _key in row[1:-1]:
                    row_rects.append(pygame.Rect(x, row_y, 122, ROW_H))
                    x += 126
                row_rects.append(pygame.Rect(x, row_y, 156, ROW_H))
            else:
                row_rects = [
                    pygame.Rect(8, row_y, 160, ROW_H),
                    pygame.Rect(172, row_y, 936, ROW_H),
                    pygame.Rect(1112, row_y, 160, ROW_H),
                ]
            self._key_rects.append(row_rects)

    def attach(self, target) -> None:
        self._target = target
        self._visible = True
        self._layer = "alpha"
        self._shift = False
        self._build_rects()

    def detach(self) -> None:
        self._target = None
        self._visible = False
        self._active_key = None

    @property
    def is_visible(self) -> bool:
        return self._visible

    def draw(self, screen: pygame.Surface) -> None:
        if not self._visible:
            return

        pygame.draw.rect(screen, COLOUR_SIDEBAR_BG[:3], pygame.Rect(0, KB_Y, SCREEN_W, KB_H))
        layer_keys = LAYERS[self._layer]
        font = self._assets.font(16)
        icon_font = self._assets.icon(24)

        for r, (row, row_rects) in enumerate(zip(layer_keys, self._key_rects)):
            for c, (key, rect) in enumerate(zip(row, row_rects)):
                is_active = self._active_key == (r, c)
                is_special = key in {"SHIFT", "BACKSPACE", "123", "#+=", "ABC", "DONE", "SPACE"}
                if is_active:
                    bg = COLOUR_KEY_BG_ACTIVE[:3]
                elif is_special:
                    bg = COLOUR_KEY_BG_SPECIAL[:3]
                else:
                    bg = COLOUR_KEY_BG[:3]
                pygame.draw.rect(screen, bg, rect, border_radius=8)

                icon = None
                if key == "SHIFT":
                    icon = IC_SHIFT_LOCK if self._shift else IC_SHIFT
                elif key == "BACKSPACE":
                    icon = IC_BACKSPACE
                elif key == "SPACE":
                    label = " "
                elif key == "DONE":
                    label = "Done"
                else:
                    label = key.upper() if self._shift else key.lower()

                if icon is not None:
                    surf, _ = icon_font.render(icon, COLOUR_TEXT_PRIMARY[:3])
                else:
                    surf, _ = font.render(label, COLOUR_TEXT_PRIMARY[:3])
                screen.blit(surf, (rect.centerx - surf.get_width() // 2, rect.centery - surf.get_height() // 2))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self._visible:
            return False

        layer_keys = LAYERS[self._layer]
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 0) == 1:
            for r, row_rects in enumerate(self._key_rects):
                for c, rect in enumerate(row_rects):
                    if rect.collidepoint(event.pos):
                        self._active_key = (r, c)
                        return True
            return False
        if event.type == pygame.MOUSEBUTTONUP and getattr(event, "button", 0) == 1 and self._active_key is not None:
            r, c = self._active_key
            self._active_key = None
            if r < len(layer_keys) and c < len(layer_keys[r]):
                self._emit(r, c)
            return True
        return False

    def _emit(self, row: int, col: int) -> None:
        key = LAYERS[self._layer][row][col]
        match key:
            case "BACKSPACE":
                if self._target:
                    self._target.backspace()
            case "SPACE":
                if self._target:
                    self._target.append(" ")
            case "DONE":
                self.detach()
                if self._on_done:
                    self._on_done()
            case "SHIFT":
                self._shift = not self._shift
            case "123":
                self._layer = "numeric"
                self._shift = False
                self._build_rects()
            case "#+=":
                self._layer = "extended"
                self._shift = False
                self._build_rects()
            case "ABC":
                self._layer = "alpha"
                self._shift = False
                self._build_rects()
            case _:
                ch = key.upper() if self._shift else key.lower()
                if self._target:
                    self._target.append(ch)
                if self._shift:
                    self._shift = False
