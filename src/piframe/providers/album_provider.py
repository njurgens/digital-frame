"""Structural type for photo album providers.

Not to be confused with the sibling module ``piframe.album_provider``
(the legacy ``DirectoryReader`` kept for the issue-43 exit criteria);
this module defines the protocol the providers implement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from piframe.album import Album
from piframe.types import SyncStatus


class AlbumProvider(Protocol):
    """Structural type for photo album providers.

    A provider is the sole owner of its image files: it decides where
    they are stored, when they are downloaded, and when they are deleted.
    Consumers read the current collection through :meth:`album` and never
    touch the provider's storage directly.
    """

    @property
    def storage_dir(self) -> Path | None:
        """Directory where the provider stores its image files.

        None when the provider has no local storage (e.g. a stub for a
        not-yet-implemented source).
        """
        ...

    def sync(self) -> Album:
        """Refresh the provider's local cache from its source.

        Runs to completion in the caller's thread.  On failure the
        provider records the error in its status before raising, and the
        previously cached album is retained.

        Returns:
            The refreshed album.

        """
        ...

    def album(self) -> Album:
        """Return a defensive copy of the current cached album.

        Returns an empty album before the first successful sync and the
        last known good album afterwards.  Never raises.
        """
        ...

    def status(self) -> SyncStatus:
        """Return a defensive copy of the current sync status. Never raises."""
        ...

    def close(self) -> None:
        """Release held resources.

        Idempotent; safe to call multiple times.  No further ``sync`` or
        ``album`` calls should be made after close.
        """
        ...
