from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

# Screen constants
SCREEN_W = 1280
SCREEN_H = 800
RIGHT_COL_W = 80
SIDEBAR_W = 333
BOTTOM_BAR_H = 88
SETTINGS_CONTENT_X = SIDEBAR_W
SETTINGS_CONTENT_W = SCREEN_W - SIDEBAR_W
FPS = 30
TRANS_DURATION = 0.5
OVERLAY_DISMISS = 5.0
WAKE_GRACE = 30.0


class AppState(Enum):
    SLIDESHOW = auto()
    OVERLAY = auto()
    SETTINGS = auto()
    KEYBOARD = auto()
    SLEEPING = auto()


class AppEvent(Enum):
    SLEEP = auto()
    WAKE = auto()
    SYNC_COMPLETE = auto()
    OVERLAY_DISMISS = auto()


EVT_SYNC_COMPLETE: int | None = None
EVT_SLEEP: int | None = None
EVT_WAKE: int | None = None
EVT_UPDATE_RESULT: int | None = None
EVT_WIFI_RESULT: int | None = None


def init_events() -> None:
    import pygame

    global EVT_SYNC_COMPLETE, EVT_SLEEP, EVT_WAKE, EVT_UPDATE_RESULT, EVT_WIFI_RESULT
    EVT_SYNC_COMPLETE = pygame.USEREVENT + 1
    EVT_SLEEP = pygame.USEREVENT + 2
    EVT_WAKE = pygame.USEREVENT + 3
    EVT_UPDATE_RESULT = pygame.USEREVENT + 4
    EVT_WIFI_RESULT = pygame.USEREVENT + 5


@dataclass
class SyncStatus:
    last_sync_time: datetime | None = None
    photo_count: int = 0
    in_progress: bool = False
    last_error: str | None = None


@dataclass
class WifiNetwork:
    ssid: str
    security: str
    signal: int

    @property
    def signal_level(self) -> int:
        if self.signal >= 67:
            return 2
        if self.signal >= 34:
            return 1
        return 0


@dataclass
class WifiStatus:
    connected: bool
    ssid: str
    ip_address: str


@dataclass
class WifiResult:
    operation: str
    success: bool
    data: object | None = None
    error: str | None = None


@dataclass
class UpdateResult:
    available: bool
    tag_name: str = ""
    tarball_url: str = ""
    error: str | None = None


# Colour palette
COLOUR_SCRIM = (0, 0, 0, 140)
COLOUR_OVERLAY_BTN_BG = (255, 255, 255, 30)
COLOUR_OVERLAY_BTN_BD = (255, 255, 255, 51)
COLOUR_PROGRESS_BAR = (255, 255, 255, 179)
COLOUR_SIDEBAR_BG = (24, 24, 24, 255)
COLOUR_CONTENT_BG = (17, 17, 17, 255)
COLOUR_NAV_ACTIVE_BG = (255, 255, 255, 23)
COLOUR_TOGGLE_ON = (55, 138, 221, 255)
COLOUR_TOGGLE_OFF = (80, 80, 80, 255)
COLOUR_TOGGLE_THUMB = (255, 255, 255, 255)
COLOUR_DESTRUCTIVE = (242, 75, 74, 255)
COLOUR_CONNECTED = (83, 74, 183, 255)
COLOUR_TEXT_PRIMARY = (255, 255, 255, 255)
COLOUR_TEXT_SECONDARY = (153, 153, 153, 255)
COLOUR_TEXT_CAPTION = (102, 102, 102, 255)
COLOUR_DIVIDER = (255, 255, 255, 20)
COLOUR_SLIDER_TRACK = (255, 255, 255, 51)
COLOUR_SLIDER_THUMB = (255, 255, 255, 255)
COLOUR_SLIDER_FILL = (255, 255, 255, 179)
COLOUR_KEY_BG = (50, 50, 50, 255)
COLOUR_KEY_BG_SPECIAL = (80, 80, 80, 255)
COLOUR_KEY_BG_ACTIVE = (100, 100, 100, 255)
COLOUR_SCROLL_PICKER_HL = (255, 255, 255, 25)
COLOUR_PILL_BG = (50, 50, 50, 255)
COLOUR_PILL_BORDER = (255, 255, 255, 51)
COLOUR_DIALOG_BG = (30, 30, 30, 245)
COLOUR_DIALOG_BORDER = (255, 255, 255, 30)
COLOUR_BTN_PRIMARY = (55, 138, 221, 255)
COLOUR_BTN_SECONDARY = (60, 60, 60, 255)
COLOUR_WIFI_STRENGTH_0 = (80, 80, 80, 255)
COLOUR_WIFI_STRENGTH_1 = (255, 255, 255, 255)
COLOUR_CLOCK_TEXT = (255, 255, 255, 220)
COLOUR_OVERLAY_SCRIM = (0, 0, 0, 90)
