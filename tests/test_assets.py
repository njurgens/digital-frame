"""Tests for asset loading."""

from __future__ import annotations

import os
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pygame.freetype
import pytest


@pytest.fixture(scope="module", autouse=True)
def pg() -> None:
    """Initialise pygame for the test module."""
    pygame.init()
    pygame.display.set_mode((1280, 800))


def test_brightness_icon_codepoints_are_distinct_sun_glyphs() -> None:
    """Brightness slider icons use distinct brightness_high/low codepoints."""
    from piframe import assets as assets_mod

    assert assets_mod.IC_BRIGHTNESS_HIGH == "\ue1ac"
    assert assets_mod.IC_BRIGHTNESS_LOW == "\ue1ad"
    assert assets_mod.IC_BRIGHTNESS_HIGH != assets_mod.IC_BRIGHTNESS_LOW
    # The old U+E896 constant (the Material "list" glyph) must not come back.
    assert not hasattr(assets_mod, "IC_BRIGHTNESS")


def test_skip_icon_codepoints_are_material_skip_glyphs() -> None:
    """Transport-row skip buttons use the correct Material skip glyphs."""
    from piframe import assets as assets_mod

    # In the bundled Material Icons font (v1.017), U+E045 is skip_previous
    # and U+E044 is skip_next; U+E043 is shuffle.
    assert assets_mod.IC_SKIP_PREV == "\ue045"
    assert assets_mod.IC_SKIP_NEXT == "\ue044"


def test_assets_load_creates_font_instances(monkeypatch: pytest.MonkeyPatch) -> None:
    """Assets.load() creates pygame.freetype.Font for each size/font."""
    from piframe import assets as assets_mod

    fonts_created: list[tuple[str, int]] = []

    def mock_font(path: str, size: int) -> pygame.Surface:
        fonts_created.append((path, size))
        return pygame.Surface((1, 1))

    monkeypatch.setattr(pygame.freetype, "Font", mock_font)

    # Temporarily override the font paths so mock is called
    orig_regular = assets_mod._REGULAR
    orig_bold = assets_mod._BOLD
    orig_icons = assets_mod._ICONS
    assets_mod._REGULAR = str(Path("fonts/NotoSans-Regular.ttf"))
    assets_mod._BOLD = str(Path("fonts/NotoSans-Bold.ttf"))
    assets_mod._ICONS = str(Path("fonts/MaterialIcons-Regular.ttf"))

    try:
        asset_inst = assets_mod.Assets.load()
    finally:
        assets_mod._REGULAR = orig_regular
        assets_mod._BOLD = orig_bold
        assets_mod._ICONS = orig_icons

    # 6 sizes x 2 font files (regular + bold) + 3 icon sizes = 15 font loads
    assert len(fonts_created) == 15

    # Verify the sizes match the expected sets
    regular_sizes = sorted(size for path, size in fonts_created if "NotoSans-Regular" in path)
    bold_sizes = sorted(size for path, size in fonts_created if "NotoSans-Bold" in path)
    icon_sizes = sorted(size for path, size in fonts_created if "MaterialIcons" in path)

    assert regular_sizes == [14, 16, 18, 20, 24, 48]
    assert bold_sizes == [14, 16, 18, 20, 24, 48]
    assert icon_sizes == [20, 24, 32]

    assert asset_inst._regular is not None
    assert asset_inst._bold is not None
    assert asset_inst._icons is not None
