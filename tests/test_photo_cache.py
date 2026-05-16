from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from piframe.photo_cache import MAX_CACHE, PhotoCache


@pytest.mark.skipif(pytest.importorskip("PIL", reason="PIL is required") is None, reason="PIL is required")
def test_cache_key_format(tmp_path: Path):
    cache = PhotoCache((1280, 800))
    p = tmp_path / "hello-world.jpg"
    key = cache._key(p, "fit")
    assert key == "hello-world_fit_v2"


def test_lru_eviction():
    cache = PhotoCache((1280, 800))
    for i in range(MAX_CACHE + 1):
        cache._put(f"k{i}", pygame.Surface((10, 10)))

    assert len(cache._cache) == MAX_CACHE
    assert "k0" not in cache._cache
    assert f"k{MAX_CACHE}" in cache._cache


def test_exif_orientation_dimensions(tmp_path: Path):
    PIL = pytest.importorskip("PIL")
    Image = PIL.Image

    cache = PhotoCache((1280, 800))

    for tag in range(1, 9):
        p = tmp_path / f"exif_{tag}.jpg"
        img = Image.new("RGB", (40, 20), color=(255, 0, 0))
        exif = Image.Exif()
        exif[274] = tag
        img.save(p, format="JPEG", exif=exif)

        loaded = Image.open(p)
        oriented = cache._apply_exif_orientation(loaded)

        if tag in {5, 6, 7, 8}:
            assert oriented.size == (20, 40)
        else:
            assert oriented.size == (40, 20)
