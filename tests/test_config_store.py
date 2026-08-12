"""Tests for ConfigStore loading, merging, and flushing."""

import os
import time
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

from piframe.config_store import ConfigStore


def write_toml(path: Path, content: str) -> None:
    """Write toml."""
    path.write_text(content)


def test_load_from_file(tmp_path: Path) -> None:
    """Load from file."""
    p = tmp_path / "config.toml"
    write_toml(p, "[slideshow]\ninterval = 15\n")
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 15.0


def test_load_missing_file_uses_defaults(tmp_path: Path) -> None:
    """Load missing file uses defaults."""
    p = tmp_path / "nonexistent.toml"
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 30.0
    assert cfg.display.brightness == 72


def test_load_malformed_toml_creates_backup(tmp_path: Path) -> None:
    """Load malformed toml creates backup."""
    p = tmp_path / "config.toml"
    p.write_text("this is not valid [[[ toml")
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 30.0
    assert (tmp_path / "config.bak").exists()


def test_interval_clamped_below_min(tmp_path: Path) -> None:
    """Interval clamped below min."""
    p = tmp_path / "config.toml"
    write_toml(p, "[slideshow]\ninterval = -5.0\n")
    cfg = ConfigStore(p)
    assert cfg.slideshow.interval == 1.0


def test_brightness_clamped_above_max(tmp_path: Path) -> None:
    """Brightness clamped above max."""
    p = tmp_path / "config.toml"
    write_toml(p, "[display]\nbrightness = 200\n")
    cfg = ConfigStore(p)
    assert cfg.display.brightness == 100


def test_set_and_debounce_write(tmp_path: Path) -> None:
    """Set and debounce write."""
    p = tmp_path / "config.toml"
    cfg = ConfigStore(p)
    now = time.monotonic()
    cfg.set("display", "brightness", 42)
    cfg.tick(now + 0.3)
    assert not p.exists() or "42" not in p.read_text()
    cfg.tick(now + 0.6)
    assert p.exists()
    assert "42" in p.read_text()


def test_flush_now_writes_immediately(tmp_path: Path) -> None:
    """Flush now writes immediately."""
    p = tmp_path / "config.toml"
    cfg = ConfigStore(p)
    cfg.set("display", "brightness", 77)
    cfg.flush_now()
    assert p.exists()
    assert "77" in p.read_text()


def test_protected_keys_never_overwritten(tmp_path: Path) -> None:
    """Protected keys never overwritten."""
    p = tmp_path / "config.toml"
    write_toml(
        p,
        "[sync]\n"
        'share_url = "https://secret"\n'
        'password = "pw"\n'
        'output_dir = "/data"\n'
        'cache_dir = "/cache"\n',
    )
    cfg = ConfigStore(p)
    cfg.set("sync", "share_url", "OVERWRITTEN")
    cfg.flush_now()
    content = p.read_text()
    assert "OVERWRITTEN" not in content
    assert "https://secret" in content
