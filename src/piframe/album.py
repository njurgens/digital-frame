"""An album: an immutable snapshot of the images available for display."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from piframe.image import Image


@dataclass(frozen=True, slots=True)
class Album:
    """Immutable snapshot of the images currently available for display.

    Membership is fixed at construction time.  The backing tuple is
    immutable, so a defensive copy (a new ``Album`` wrapping the same
    tuple) never exposes mutable state to callers.
    """

    _images: tuple[Image, ...] = ()

    @classmethod
    def from_images(cls, images: Iterable[Image]) -> Album:
        """Build an album from an iterable of images."""
        return cls(tuple(images))

    @property
    def images(self) -> tuple[Image, ...]:
        """The immutable tuple of images in this album."""
        return self._images

    def __len__(self) -> int:
        """Number of images in this album."""
        return len(self._images)

    def __iter__(self) -> Iterator[Image]:
        """Iterate over the images in this album."""
        return iter(self._images)

    def __getitem__(self, index: int) -> Image:
        """Indexed access to the images in this album."""
        return self._images[index]
