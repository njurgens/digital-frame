#!/usr/bin/env python3
"""Render the Pi Frame app headless and save a screenshot."""
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Must be set before any pygame import
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pygame.freetype

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from piframe.assets import Assets
from piframe.config_store import ConfigStore
from piframe.types import SCREEN_W, SCREEN_H, init_events
from piframe.photo_cache import PhotoCache
from piframe.clock_widget import ClockWidget
from piframe.app import SlideshowPlayer


def main():
    pygame.init()
    pygame.freetype.init()
    init_events()

    # Create a dummy display
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))

    # Create a temporary config with test directories
    config_dir = Path("/tmp/test_config")
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.toml"
    
    # Write a minimal config
    config_path.write_text("""
[slideshow]
interval = 30
fit_mode = "fit"
shuffle = true
transition = "crossfade"

[display]
brightness = 72
show_clock = true
timezone_auto = true

[sleep]
enabled = false
sleep_time = "22:00"
wake_time = "07:00"

[sync]
share_url = ""
password = ""
output_dir = "/tmp/test_photos"
cache_dir = "/tmp/test_cache"
interval_minutes = 60

[system]
timezone = "America/Los_Angeles"

[update]
repo = "njurgens/digital-frame"
""")

    config = ConfigStore(config_path)

    # Create test photos directory with a dummy image
    output_dir = Path("/tmp/test_photos")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a test image
    test_surf = pygame.Surface((SCREEN_W, SCREEN_H))
    test_surf.fill((30, 30, 60))
    pygame.image.save(test_surf, output_dir / "test.jpg")

    # Create cache directory
    cache_dir = Path("/tmp/test_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load assets
    assets = Assets.load()

    # Create photo cache
    cache = PhotoCache(cache_dir=cache_dir)

    # Mock backlight (no /sys/class/backlight in Docker)
    with patch("piframe.backlight.open"):
        from piframe.backlight import BacklightController
        backlight = BacklightController()

    # Create player
    player = SlideshowPlayer(config, cache, (SCREEN_W, SCREEN_H), assets)

    # Create clock widget
    clock_w = ClockWidget(assets)

    # Draw the slideshow state
    player.draw(screen)
    if config.display.show_clock:
        clock_w.draw(screen)

    # Save screenshot
    out = Path("/tmp/headless_screenshot.png")
    pygame.image.save(screen, str(out))
    print(f"Screenshot saved to {out}")

    pygame.quit()


if __name__ == "__main__":
    main()
