from __future__ import annotations

from pathlib import Path

import pygame.freetype

FONT_SIZE_CLOCK = 48
FONT_SIZE_HEADING = 24
FONT_SIZE_BODY = 18
FONT_SIZE_NAV = 20
FONT_SIZE_SECONDARY = 14
FONT_SIZE_KEY = 16
ICON_SIZE_NORMAL = 24
ICON_SIZE_OVERLAY = 32

IC_SETTINGS = "\ue8b8"
IC_PLAY = "\ue037"
IC_PAUSE = "\ue034"
IC_SKIP_PREV = "\ue044"
IC_SKIP_NEXT = "\ue043"
IC_ARROW_BACK = "\ue5d5"
IC_ARROW_FWD = "\ue5dc"
IC_INFO = "\ue87d"
IC_WIFI = "\ue8f4"
IC_WIFI_OFF = "\ue8f5"
IC_LOCK = "\ue897"
IC_SYNC = "\ue1d8"
IC_CLOSE = "\ue5cd"
IC_CHECK = "\ue876"
IC_CHEVRON_L = "\ue5c4"
IC_CHEVRON_R = "\ue5c8"
IC_EXPAND_MORE = "\ue5cf"
IC_EXPAND_LESS = "\ue5ce"
IC_BRIGHTNESS = "\ue896"
IC_SCHEDULE = "\ue8b5"
IC_PERSON = "\ue7ef"
IC_DELETE = "\ue872"

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"
_REGULAR = str(_FONT_DIR / "NotoSans-Regular.ttf")
_BOLD = str(_FONT_DIR / "NotoSans-Bold.ttf")
_ICONS = str(_FONT_DIR / "MaterialIcons-Regular.ttf")


class Assets:
    def __init__(self) -> None:
        self._regular: dict[int, pygame.freetype.Font] = {}
        self._bold: dict[int, pygame.freetype.Font] = {}
        self._icons: dict[int, pygame.freetype.Font] = {}

    @classmethod
    def load(cls) -> "Assets":
        inst = cls()
        inst._regular = {
            size: pygame.freetype.Font(_REGULAR, size)
            for size in [14, 16, 18, 20, 24, 48]
        }
        inst._bold = {
            size: pygame.freetype.Font(_BOLD, size) for size in [14, 16, 18, 20, 24, 48]
        }
        inst._icons = {size: pygame.freetype.Font(_ICONS, size) for size in [24, 32]}
        return inst

    def font(self, size: int) -> pygame.freetype.Font:
        return self._regular[size]

    def font_bold(self, size: int) -> pygame.freetype.Font:
        return self._bold[size]

    def icon(self, size: int) -> pygame.freetype.Font:
        return self._icons[size]
