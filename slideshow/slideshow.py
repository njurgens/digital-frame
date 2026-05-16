#!/usr/bin/env python3
"""
slideshow.py — pygame-based picture frame slideshow.

Displays JPEG/PNG images with blurred background fill and crossfade transitions.
Rescans the image directory at the start of each cycle so new synced images
appear automatically without restarting.

Usage:
    python3 slideshow.py
"""

import logging
import os
import random
import time
import tomllib
from pathlib import Path
from threading import Thread

import pygame
from PIL import Image, ExifTags

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).parent
_CONFIG_PATH = _BASE_DIR / "config.toml"

_DEFAULTS: dict = {
    "output_dir": "/home/frame/Pictures/slideshow",
    "cache_dir": "/home/frame/.cache/framesync",
    "display_duration": 15,
    "transition_duration": 1.5,
    "preload_delay": 3,
}

def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "rb") as f:
            cfg.update(tomllib.load(f))
    return cfg

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Quit flag set by check_events(); avoids re-consuming events after they're handled.
_quit_requested = False

# ---------------------------------------------------------------------------
# Event pump
# ---------------------------------------------------------------------------

def check_events() -> bool:
    """Drain the pygame event queue. Returns False if the app should quit."""
    global _quit_requested
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            _quit_requested = True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            _quit_requested = True
    return not _quit_requested

# ---------------------------------------------------------------------------
# Image surface preparation
# ---------------------------------------------------------------------------

def _load_image_corrected(path: Path) -> pygame.Surface:
    """Load image via PIL to honour EXIF orientation, return a pygame Surface."""
    pil_img = Image.open(path)
    # Apply EXIF rotation if present
    try:
        exif = pil_img.getexif()
        orientation_tag = next(
            tag for tag, name in ExifTags.TAGS.items() if name == "Orientation"
        )
        orientation = exif.get(orientation_tag)
        _EXIF_ROTATE = {3: 180, 6: 270, 8: 90}
        if orientation in _EXIF_ROTATE:
            pil_img = pil_img.rotate(_EXIF_ROTATE[orientation], expand=True)
    except Exception:
        pass  # No EXIF or unreadable — proceed as-is
    pil_img = pil_img.convert("RGB")
    return pygame.image.frombytes(pil_img.tobytes(), pil_img.size, "RGB")


def blur_surface(surface: pygame.Surface, strength: int = 8, passes: int = 3) -> pygame.Surface:
    """Multi-pass downsample/upsample blur. More passes = smoother, less pixellated."""
    result = surface
    for _ in range(passes):
        w, h = result.get_size()
        small = pygame.transform.smoothscale(result, (max(1, w // strength), max(1, h // strength)))
        result = pygame.transform.smoothscale(small, (w, h))
    return result


_CACHE_VERSION = "v3"  # bump when cache format changes (e.g. EXIF fix, blur improvement)


def prepare_surface(
    path: Path,
    size: tuple[int, int],
    cache_dir: Path | None,
) -> pygame.Surface:
    """
    Build a composite surface: blurred-fill background + aspect-correct foreground.
    Reads from / writes to a disk cache keyed by filename, mtime, screen size, and
    cache version (so EXIF-fix and other changes auto-invalidate old entries).
    """
    sw, sh = size

    if cache_dir is not None:
        mtime = int(path.stat().st_mtime)
        cache_key = f"{path.stem}-{mtime}-{sw}x{sh}-{_CACHE_VERSION}.png"
        cache_path = cache_dir / cache_key
        if cache_path.exists():
            try:
                surf = pygame.image.load(str(cache_path)).convert()
                log.debug("Cache hit: %s", cache_key)
                return surf
            except Exception as e:
                log.warning("Cache load failed for %s: %s", cache_key, e)

    img = _load_image_corrected(path).convert()
    iw, ih = img.get_size()

    # Background: scale to fill screen (larger dimension wins), crop to screen, blur
    fill_scale = max(sw / iw, sh / ih)
    fill_w, fill_h = int(iw * fill_scale), int(ih * fill_scale)
    bg = pygame.transform.smoothscale(img, (fill_w, fill_h))
    crop_x = (fill_w - sw) // 2
    crop_y = (fill_h - sh) // 2
    bg = bg.subsurface((crop_x, crop_y, sw, sh)).copy()
    bg = blur_surface(bg, strength=8)

    # Foreground: scale to fit screen (smaller dimension wins), center
    fit_scale = min(sw / iw, sh / ih)
    fit_w, fit_h = int(iw * fit_scale), int(ih * fit_scale)
    fg = pygame.transform.smoothscale(img, (fit_w, fit_h))

    composite = bg
    fx = (sw - fit_w) // 2
    fy = (sh - fit_h) // 2
    composite.blit(fg, (fx, fy))

    if cache_dir is not None:
        try:
            pygame.image.save(composite, str(cache_path))
            log.debug("Cache saved: %s", cache_key)
        except Exception as e:
            log.warning("Cache save failed: %s", e)

    return composite

# ---------------------------------------------------------------------------
# Crossfade transition
# ---------------------------------------------------------------------------

def crossfade(
    screen: pygame.Surface,
    surface_a: pygame.Surface,
    surface_b: pygame.Surface,
    duration: float,
) -> None:
    """Blend from surface_a to surface_b over `duration` seconds.

    Uses wall-clock progress so slow frames self-correct rather than
    causing the transition to run long on Pi 3A+.
    """
    steps = max(1, int(duration * 24))  # target 24fps; wall-clock progress self-corrects if Pi can't keep up
    step_budget = duration / steps
    overlay = surface_b.copy()
    start = time.monotonic()

    for i in range(steps + 1):
        elapsed = time.monotonic() - start
        progress = min(elapsed / duration, 1.0)
        overlay.set_alpha(int(255 * progress))
        screen.blit(surface_a, (0, 0))
        screen.blit(overlay, (0, 0))
        pygame.display.flip()
        # Sleep only the remaining budget for this step to avoid drift
        next_step_time = (i + 1) * step_budget
        remaining = start + next_step_time - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)

# ---------------------------------------------------------------------------
# Show one image with background preloading of the next
# ---------------------------------------------------------------------------

def show_image(
    screen: pygame.Surface,
    current_surface: pygame.Surface,
    next_path: Path,
    size: tuple[int, int],
    config: dict,
    cache_dir: Path | None,
) -> pygame.Surface | None:
    """
    Blit current_surface, wait display_duration (starting preload after
    preload_delay), then crossfade to the preloaded next surface.

    Returns the next surface on success, or None if quit was requested or
    the next image failed to load.
    """
    screen.blit(current_surface, (0, 0))
    pygame.display.flip()

    next_surface: list[pygame.Surface | None] = [None]
    preload_exc: list[Exception | None] = [None]

    def preload() -> None:
        try:
            next_surface[0] = prepare_surface(next_path, size, cache_dir)
        except Exception as e:
            preload_exc[0] = e

    t = Thread(target=preload, daemon=True)

    preload_delay = float(config["preload_delay"])
    display_duration = float(config["display_duration"])
    transition_duration = float(config["transition_duration"])

    # Wait preload_delay before starting background load
    deadline = time.monotonic() + preload_delay
    while time.monotonic() < deadline:
        if not check_events():
            return None
        time.sleep(0.05)

    t.start()

    # Wait the rest of the display time
    deadline = time.monotonic() + (display_duration - preload_delay)
    while time.monotonic() < deadline:
        if not check_events():
            return None
        time.sleep(0.05)

    t.join()

    if preload_exc[0]:
        log.error("Failed to load %s: %s — skipping", next_path.name, preload_exc[0])
        return None

    crossfade(screen, current_surface, next_surface[0], transition_duration)
    return next_surface[0]

# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------

def scan_images(directory: Path) -> list[Path]:
    """Return a shuffled list of supported image files in directory."""
    if not directory.is_dir():
        return []
    images = [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    random.shuffle(images)
    return images

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

_PID_FILE = Path("/tmp/slideshow.pid")


def main() -> None:
    _PID_FILE.write_text(str(os.getpid()))
    try:
        _run()
    finally:
        _PID_FILE.unlink(missing_ok=True)


def _run() -> None:
    config = load_config()

    images_dir = Path(config["output_dir"])
    cache_dir_path = Path(config["cache_dir"])

    cache_dir: Path | None = cache_dir_path
    try:
        cache_dir_path.mkdir(parents=True, exist_ok=True)
        probe = cache_dir_path / ".write_test"
        probe.touch()
        probe.unlink()
    except Exception as e:
        log.warning("Cache dir not writable (%s): %s — running without cache", cache_dir_path, e)
        cache_dir = None

    pygame.init()
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.mouse.set_visible(False)
    size = screen.get_size()
    log.info("Display initialised at %dx%d", *size)

    current_surface: pygame.Surface | None = None
    running = True

    while running:
        images = scan_images(images_dir)

        if not images:
            log.warning("No images in %s — retrying in 5s", images_dir)
            screen.fill((0, 0, 0))
            pygame.display.flip()
            for _ in range(100):
                if not check_events():
                    running = False
                    break
                time.sleep(0.05)
            continue

        log.info("Starting cycle: %d image(s)", len(images))
        # current_surface intentionally NOT reset here — persists across cycle
        # boundaries so the first image of the new cycle crossfades smoothly
        # from the last image of the previous cycle.

        for path in images:
            if not running or _quit_requested:
                running = False
                break

            if current_surface is None:
                # Very first image (startup or after a load error): hard-show,
                # no fade since there's nothing to fade from.
                try:
                    current_surface = prepare_surface(path, size, cache_dir)
                except Exception as e:
                    log.error("Failed to load %s: %s — skipping", path.name, e)
                    continue
                screen.blit(current_surface, (0, 0))
                pygame.display.flip()
                deadline = time.monotonic() + float(config["display_duration"])
                while time.monotonic() < deadline:
                    if not check_events():
                        running = False
                        break
                    time.sleep(0.05)
                continue

            # Crossfade from whatever is on screen (current_surface) to path.
            result = show_image(screen, current_surface, path, size, config, cache_dir)

            if result is None:
                if _quit_requested:
                    running = False
                    break
                current_surface = None
                continue

            current_surface = result

    pygame.quit()
    log.info("Slideshow exited cleanly.")


if __name__ == "__main__":
    main()
