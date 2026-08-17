"""Shared implementation for album providers."""

from __future__ import annotations

import copy
import logging
import threading
import time
from datetime import datetime

from piframe.album import Album
from piframe.types import SyncStatus

#: How long close() waits for an in-flight sync before closing anyway.
CLOSE_SYNC_TIMEOUT = 60.0


class BaseAlbumProvider:
    """Base class implementing the album provider lifecycle.

    Concrete providers implement :meth:`_do_sync` with their source
    specific work.  The base class owns the cached album and the sync
    status: status fields are mutated under a lock and always handed out
    as defensive copies, while the album reference is swapped atomically
    (the GIL protects the assignment).  A failed sync therefore never
    destroys the last known good album.
    """

    def __init__(self) -> None:
        """Initialise the cached album, status, and lifecycle state."""
        self._album: Album = Album()
        self._status: SyncStatus = SyncStatus()
        self._status_lock = threading.Lock()
        self._closed: bool = False
        self._sync_in_flight: bool = False
        self._sync_cond = threading.Condition()

    # -- AlbumProvider protocol -------------------------------------------

    def sync(self) -> Album:
        """Run a sync, managing the status lifecycle around provider work.

        On failure the error is recorded in the status before the
        exception is re-raised, so callers (the sync service) only need to
        catch and log.  Refuses to run once the provider is closed, so a
        late trigger cannot use a released provider.
        """
        with self._sync_cond:
            if self._closed:
                raise RuntimeError("provider is closed; no further syncs")
            self._sync_in_flight = True
        try:
            self._begin_sync()
            try:
                album = self._do_sync()
            except Exception as exc:
                self._fail_sync(str(exc))
                raise
            self._finish_sync(album)
            return album
        finally:
            with self._sync_cond:
                self._sync_in_flight = False
                self._sync_cond.notify_all()

    def album(self) -> Album:
        """Return a defensive copy of the current cached album."""
        with self._status_lock:
            return Album.from_images(self._album.images)

    def status(self) -> SyncStatus:
        """Return a defensive copy of the current sync status."""
        with self._status_lock:
            return copy.copy(self._status)

    def close(self) -> None:
        """Release held resources. Idempotent.

        Waits up to :data:`CLOSE_SYNC_TIMEOUT` seconds for an in-flight
        sync to finish first, so no caller uses the provider after it is
        closed (the design's "no live caller after close" guarantee).
        """
        if self._closed:
            return
        deadline = time.monotonic() + CLOSE_SYNC_TIMEOUT
        with self._sync_cond:
            while self._sync_in_flight:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logging.warning(
                        "Provider close: sync still in flight after %.0fs; closing anyway",
                        CLOSE_SYNC_TIMEOUT,
                    )
                    break
                self._sync_cond.wait(remaining)
            # Set under the lock: sync() checks the flag under the same lock,
            # so a close can never land between that check and the in-flight
            # flag being set.
            self._closed = True
        self._release()

    # -- Hooks for subclasses ----------------------------------------------

    def _do_sync(self) -> Album:
        """Perform the source specific sync work and return the new album."""
        raise NotImplementedError

    def _release(self) -> None:
        """Release held resources. Called once, from :meth:`close`."""

    # -- Status lifecycle ----------------------------------------------------

    def _begin_sync(self) -> None:
        with self._status_lock:
            self._status.in_progress = True
            self._status.last_error = None

    def _finish_sync(self, album: Album) -> None:
        now = datetime.now()
        with self._status_lock:
            self._album = album
            self._status.in_progress = False
            self._status.photo_count = len(album)
            self._status.last_sync_time = now

    def _fail_sync(self, error: str) -> None:
        with self._status_lock:
            self._status.in_progress = False
            self._status.last_error = error
            self._status.last_sync_time = datetime.now()

    def _note_error(self, message: str) -> None:
        """Record a non-fatal error in the status without failing the sync."""
        with self._status_lock:
            self._status.last_error = message
