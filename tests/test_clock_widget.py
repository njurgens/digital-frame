from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pygame

from piframe.clock_widget import ClockWidget


def _mock_assets():
    assets = MagicMock()
    bold_font = MagicMock()
    body_font = MagicMock()
    bold_font.render.return_value = (pygame.Surface((100, 30)), pygame.Rect(0, 0, 100, 30))
    body_font.render.return_value = (pygame.Surface((140, 20)), pygame.Rect(0, 0, 140, 20))
    assets.font_bold.return_value = bold_font
    assets.font.return_value = body_font
    return assets, bold_font, body_font


def test_time_and_date_format_strings():
    assets, bold_font, body_font = _mock_assets()
    clock = ClockWidget(assets)
    try:
        bold_font.render.reset_mock()
        body_font.render.reset_mock()

        now = datetime(2025, 5, 16, 9, 5, tzinfo=ZoneInfo("America/Los_Angeles"))
        clock._render_surfaces(now)

        assert bold_font.render.call_args[0][0] == "9:05 AM"
        assert body_font.render.call_args[0][0] == "Friday, May 16"
    finally:
        clock.stop()


def test_update_timezone_changes_timezone():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        clock.update_timezone("UTC")
        assert clock._timezone.key == "UTC"
    finally:
        clock.stop()


def test_surfaces_rendered_after_construction():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        deadline = time.time() + 1.0
        while clock._surfaces is None and time.time() < deadline:
            time.sleep(0.02)
        assert clock._surfaces is not None
    finally:
        clock.stop()
