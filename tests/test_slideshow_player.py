"""Tests for SlideshowPlayer transitions and playlist management."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pygame

from piframe.album import Album
from piframe.image import Image
from piframe.slideshow_player import SlideshowPlayer
from piframe.types import TRANS_DURATION, SyncStatus


class StubAlbumProvider:
    """Test double for the album provider protocol."""

    def __init__(self, album: Album) -> None:
        """Store the album the double will serve."""
        self._album = album
        self.closed: bool = False

    @property
    def storage_dir(self) -> Path | None:
        """The double stores no files."""
        return None

    def sync(self) -> Album:
        """Return the stored album."""
        return self._album

    def album(self) -> Album:
        """Return the stored album."""
        return self._album

    def status(self) -> SyncStatus:
        """Return a fresh, empty status."""
        return SyncStatus()

    def close(self) -> None:
        """Record that the double was closed."""
        self.closed = True


def _make_config() -> MagicMock:
    cfg = MagicMock()
    cfg.slideshow.interval = 1.0
    cfg.slideshow.fit_mode = "fit"
    cfg.slideshow.shuffle = True
    cfg.slideshow.transition = "crossfade"
    return cfg


def _make_files(photo_dir: Path, n: int = 3) -> list[Path]:
    paths: list[Path] = []
    for i in range(n):
        p = photo_dir / f"img{i}.jpg"
        p.write_bytes(b"x")
        paths.append(p)
    return paths


def _make_provider(photo_dir: Path, n: int = 3) -> StubAlbumProvider:
    return StubAlbumProvider(Album.from_images([Image(p) for p in _make_files(photo_dir, n)]))


def _make_surface() -> pygame.Surface:
    return pygame.Surface((1280, 800))


def test_fisher_yates_contains_same_items(tmp_path: Path) -> None:
    """Fisher yates contains same items."""
    cfg = _make_config()
    provider = StubAlbumProvider(Album())
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    items = ["a", "b", "c", "d", "e", "f"]
    shuffled = player._fisher_yates(items)

    assert sorted(shuffled) == sorted(items)
    assert len(shuffled) == len(items)


def test_interval_timer_and_advance(tmp_path: Path) -> None:
    """Interval timer and advance."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 3)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    start_index = player._index
    player.update(cfg.slideshow.interval - 0.1)
    assert player._index == start_index
    assert player._in_transition is False

    player.update(0.2)
    assert player._in_transition is True
    assert player._index == (start_index + 1) % len(player._playlist)


def test_transition_progress_and_clamp(tmp_path: Path) -> None:
    """Transition progress and clamp."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 3)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    player.skip()
    assert player._trans_t == 0.0
    assert player._in_transition is True

    player._trans_start = time.monotonic() - (TRANS_DURATION / 2)
    player.update(0.0)
    assert 0.45 <= player._trans_t <= 0.55

    player._trans_start = time.monotonic() - TRANS_DURATION
    player.update(0.0)
    assert player._trans_t == 1.0
    assert player._in_transition is False
    assert player._next_surf is None


def test_advance_forward_and_backward(tmp_path: Path) -> None:
    """Advance forward and backward."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 4)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    start_index = player._index
    player.advance(direction=1)
    assert player._index == (start_index + 1) % len(player._playlist)

    player.update(TRANS_DURATION)
    after_forward = player._index
    player.go_back()
    assert player._index == (after_forward - 1) % len(player._playlist)


def test_paused_stops_update(tmp_path: Path) -> None:
    """Paused stops update."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 3)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    player.is_paused = True
    player.update(cfg.slideshow.interval + 1.0)

    assert player._in_transition is False
    assert player._elapsed == 0.0


def test_go_back_and_skip_start_transitions_with_direction(tmp_path: Path) -> None:
    """Go back and skip start transitions with direction."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 3)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    player.go_back()
    assert player._in_transition is True
    assert player._direction == -1

    player.update(TRANS_DURATION)
    player.skip()
    assert player._in_transition is True
    assert player._direction == 1


def test_rescan_builds_playlist_from_provider_album(tmp_path: Path) -> None:
    """Rescan builds the playlist from the provider's album, not a directory."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 3)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    assert sorted(player._playlist) == sorted(_make_files(tmp_path, 3))
    assert player._current_surf is not None


def test_rescan_picks_up_album_changes(tmp_path: Path) -> None:
    """Rescan reflects a refreshed album from the provider."""
    cfg = _make_config()
    provider = _make_provider(tmp_path, 3)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    (tmp_path / "img3.jpg").write_bytes(b"x")
    (tmp_path / "img4.jpg").write_bytes(b"x")
    provider._album = Album.from_images([Image(p) for p in sorted(tmp_path.iterdir())])

    player.rescan()
    assert len(player._playlist) == 5


def test_rescan_filters_non_image_paths(tmp_path: Path) -> None:
    """Rescan drops non-image paths even if a provider returns them."""
    cfg = _make_config()
    (tmp_path / "photo.jpg").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    album = Album.from_images([Image(tmp_path / "photo.jpg"), Image(tmp_path / "notes.txt")])
    provider = StubAlbumProvider(album)
    cache = MagicMock()
    cache.get.return_value = _make_surface()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    assert player._playlist == [tmp_path / "photo.jpg"]


def test_rescan_empty_album_yields_empty_playlist(tmp_path: Path) -> None:
    """Rescan with an empty album leaves the player with no slides."""
    cfg = _make_config()
    provider = StubAlbumProvider(Album())
    cache = MagicMock()
    player = SlideshowPlayer(cfg, provider=provider, cache=cache, screen_size=(1280, 800))

    assert player._playlist == []
    assert player._current_surf is None
    cache.get.assert_not_called()
