from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
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

        assert bold_font.render.call_args[0][0] == "9:05"
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


def test_update_timezone_changes_formatted_output():
    assets, bold_font, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        instant = datetime(2025, 5, 16, 16, 5, tzinfo=ZoneInfo("UTC"))

        clock.update_timezone("America/Los_Angeles")
        bold_font.render.reset_mock()
        clock._render_surfaces(instant.astimezone(clock._timezone))
        la_text = bold_font.render.call_args[0][0]

        clock.update_timezone("UTC")
        bold_font.render.reset_mock()
        clock._render_surfaces(instant.astimezone(clock._timezone))
        utc_text = bold_font.render.call_args[0][0]

        assert la_text != utc_text
    finally:
        clock.stop()


def test_ticker_marks_clock_dirty():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        clock._stop_event.set()
        clock._thread.join(timeout=1)
        clock._dirty = False
        clock._stop_event.clear()

        def _wait_once(_timeout):
            clock._stop_event.set()
            return True

        with patch.object(clock._stop_event, "wait", side_effect=_wait_once):
            clock._ticker()

        assert clock._dirty is True
        assert clock._pending_now is not None
    finally:
        clock.stop()


def test_tick_marks_clock_dirty():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        clock._dirty = False
        clock._pending_now = None
        clock.tick()
        assert clock._dirty is True
        assert clock._pending_now is not None
    finally:
        clock.stop()


def test_surfaces_rendered_after_construction():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        assert clock._surfaces is not None
    finally:
        clock.stop()


def test_draw_renders_translucent_background_bubble():
    assets = MagicMock()
    bold_font = MagicMock()
    body_font = MagicMock()
    transparent_time = pygame.Surface((100, 30), pygame.SRCALPHA)
    transparent_time.fill((0, 0, 0, 0))
    transparent_date = pygame.Surface((140, 20), pygame.SRCALPHA)
    transparent_date.fill((0, 0, 0, 0))
    bold_font.render.return_value = (transparent_time, pygame.Rect(0, 0, 100, 30))
    body_font.render.return_value = (transparent_date, pygame.Rect(0, 0, 140, 20))
    assets.font_bold.return_value = bold_font
    assets.font.return_value = body_font

    clock = ClockWidget(assets)
    try:
        screen = pygame.Surface((320, 200), pygame.SRCALPHA)
        screen.fill((255, 255, 255, 255))
        clock.draw(screen)
        assert screen.get_at((20, 20))[:3] != (255, 255, 255)
        assert screen.get_at((2, 2))[:3] == (255, 255, 255)
    finally:
        clock.stop()


def test_set_visible_hides_clock_draw():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        screen = pygame.Surface((320, 200), pygame.SRCALPHA)
        screen.fill((255, 255, 255, 255))
        clock.set_visible(False)
        clock.draw(screen)
        assert screen.get_at((20, 20))[:3] == (255, 255, 255)
    finally:
        clock.stop()


def test_set_timezone_alias_updates_timezone():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        clock.set_timezone("UTC")
        assert clock._timezone.key == "UTC"
    finally:
        clock.stop()


def test_default_timezone_falls_back_to_etc_timezone_value():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        with patch("piframe.clock_widget.Path.resolve", side_effect=OSError), patch(
            "piframe.clock_widget.Path.read_text", return_value="UTC\n"
        ):
            tz = clock._default_timezone()
        assert isinstance(tz, ZoneInfo)
        assert tz.key == "UTC"
    finally:
        clock.stop()


def test_default_timezone_falls_back_to_utc_when_sources_fail():
    assets, _, _ = _mock_assets()
    clock = ClockWidget(assets)
    try:
        with patch("piframe.clock_widget.Path.resolve", side_effect=OSError), patch(
            "piframe.clock_widget.Path.read_text", side_effect=OSError
        ):
            tz = clock._default_timezone()
        assert isinstance(tz, ZoneInfo)
        assert tz.key == "UTC"
    finally:
        clock.stop()
