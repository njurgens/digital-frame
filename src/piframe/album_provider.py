"""Legacy directory scanner retained for issue-43 exit criteria.

``DirectoryReader`` is not used by the application: the slideshow player
builds its playlist from the active album provider's collection.  It is
kept because the issue-43 exit criteria require it to keep working.  The
local provider supersedes it for any new use.

Note the name collision: this module is *not* the provider protocol —
that lives in ``piframe.providers.album_provider``.
"""

from __future__ import annotations

from pathlib import Path

from piframe.image import IMAGE_EXTENSIONS


class DirectoryReader:
    """Read supported image files from a directory via ``Path.iterdir()``.

    Non-recursive; matches the existing ``rescan()`` behaviour.
    """

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
            [p for p in self._directory.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]
        )
