from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pygame

from piframe.app import SlideshowPlayer
from piframe.types import TRANS_DURATION


def _make_config(photo_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        slideshow=SimpleNamespace(
            interval=1.0,
            fit_mode="fit",
            shuffle=True,
            transition="crossfade",
        ),
        sync=SimpleNamespace(output_dir=str(photo_dir)),
    )


def _make_files(photo_dir: Path, n: int = 3) -> None:
    for i in range(n):
        (photo_dir / f"img{i}.jpg").write_bytes(b"x")


def _make_surface() -> pygame.Surface:
    return pygame.Surface((1280, 800))


def test_fisher_yates_contains_same_items(tmp_path: Path):
    cfg = _make_config(tmp_path)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, cache, (1280, 800))

    items = ["a", "b", "c", "d", "e", "f"]
    shuffled = player._fisher_yates(items)

    assert sorted(shuffled) == sorted(items)
    assert len(shuffled) == len(items)


def test_interval_timer_and_advance(tmp_path: Path):
    _make_files(tmp_path, 3)
    cfg = _make_config(tmp_path)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, cache, (1280, 800))

    start_index = player._index
    player.update(cfg.slideshow.interval - 0.1)
    assert player._index == start_index
    assert player._in_transition is False

    player.update(0.2)
    assert player._in_transition is True
    assert player._index == (start_index + 1) % len(player._playlist)


def test_transition_progress_and_clamp(tmp_path: Path):
    _make_files(tmp_path, 3)
    cfg = _make_config(tmp_path)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, cache, (1280, 800))

    player.skip()
    assert player._trans_t == 0.0
    assert player._in_transition is True

    player.update(TRANS_DURATION / 2)
    assert 0.45 <= player._trans_t <= 0.55

    player.update(TRANS_DURATION)
    assert player._trans_t == 1.0
    assert player._in_transition is False
    assert player._next_surf is None


def test_advance_forward_and_backward(tmp_path: Path):
    _make_files(tmp_path, 4)
    cfg = _make_config(tmp_path)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, cache, (1280, 800))

    start_index = player._index
    player.advance(direction=1)
    assert player._index == (start_index + 1) % len(player._playlist)

    player.update(TRANS_DURATION)
    after_forward = player._index
    player.go_back()
    assert player._index == (after_forward - 1) % len(player._playlist)


def test_paused_stops_update(tmp_path: Path):
    _make_files(tmp_path, 3)
    cfg = _make_config(tmp_path)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, cache, (1280, 800))

    player.is_paused = True
    player.update(cfg.slideshow.interval + 1.0)

    assert player._in_transition is False
    assert player._elapsed == 0.0


def test_go_back_and_skip_start_transitions_with_direction(tmp_path: Path):
    _make_files(tmp_path, 3)
    cfg = _make_config(tmp_path)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, cache, (1280, 800))

    player.go_back()
    assert player._in_transition is True
    assert player._direction == -1

    player.update(TRANS_DURATION)
    player.skip()
    assert player._in_transition is True
    assert player._direction == 1
