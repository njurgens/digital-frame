"""Structural type for photo album providers."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from piframe.types import SyncStatus


class AlbumProvider(Protocol):
    """Structural type for photo album providers."""

    def sync(self, output_dir: Path) -> list[Path]:
        """Download new photos into *output_dir*.

        Perform destructive cleanup (delete local files not present
        remotely) and return the list of newly created files.
        """
        ...

    def status(self) -> SyncStatus:
        """Return the current sync status."""
        ...

    def stop(self) -> None:
        """Gracefully halt any in-flight sync work."""
        ...
