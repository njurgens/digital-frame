"""Album providers: supply image paths for the slideshow player."""

from __future__ import annotations

from pathlib import Path


class DirectoryReader:
    """Read supported image files from a directory via ``Path.iterdir()``.

    Non-recursive; matches the existing ``rescan()`` behaviour.
    """

    _EXTENSIONS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".gif"})

    def __init__(self, directory: str | Path) -> None:
        """Initialise with the directory to scan.

        Args:
            directory: Path to the output directory containing images.

        """
        self._directory = Path(directory)

    def get_album(self) -> list[Path]:
        """Return a sorted list of supported image paths.

        Returns:
            Sorted list of ``Path`` objects for images with extensions
            ``.jpg``, ``.jpeg``, ``.png``, or ``.gif``.  Returns an empty
            list if the directory does not exist.

        """
        if not self._directory.exists():
            return []
        return sorted(
            [p for p in self._directory.iterdir() if p.suffix.lower() in self._EXTENSIONS]
        )
