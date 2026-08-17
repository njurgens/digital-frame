"""A single photo: a file path plus lazily loaded EXIF metadata."""

from __future__ import annotations

from pathlib import Path

from piframe.exif import Exif, load_exif

#: File extensions the frame recognises as displayable photos.
IMAGE_EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".gif"})


class Image:
    """A single photo in an album.

    The EXIF payload is read from disk on first access to :attr:`exif`
    and cached on the instance, so building albums and playlists never
    pays the I/O cost (NFR-6).
    """

    __slots__ = ("_exif", "_path")

    def __init__(self, path: Path) -> None:
        """Create an image reference; EXIF metadata loads lazily."""
        self._path = path
        self._exif: Exif | None = None

    @property
    def path(self) -> Path:
        """Filesystem path of the image."""
        return self._path

    @property
    def exif(self) -> Exif | None:
        """EXIF metadata, loaded lazily on first access."""
        if self._exif is None:
            self._exif = load_exif(self._path)
        return self._exif

    def __eq__(self, other: object) -> bool:
        """Images are equal when their paths are equal."""
        return isinstance(other, Image) and self._path == other._path

    def __hash__(self) -> int:
        """Hash by path."""
        return hash(self._path)

    def __repr__(self) -> str:
        """One-line representation showing the image path."""
        return f"Image(path={self._path!r})"
