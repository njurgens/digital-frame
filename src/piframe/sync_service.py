"""Background photo sync service that polls its album provider on an interval."""

from __future__ import annotations

import logging
import threading

import pygame

from piframe import types
from piframe.config_store import ConfigStore
from piframe.providers import AlbumProvider
from piframe.types import SyncStatus


class SyncService:
    """Background sync service that runs its provider's sync on an interval.

    The provider owns the sync status: it sets in-progress, photo count,
    last sync time, and last error during :meth:`AlbumProvider.sync`.  The
    service only catches exceptions from a failed sync, logs them, and
    posts the sync-complete event; the last known good album is retained by
    the provider (FR-12).
    """

    def __init__(self, config: ConfigStore, *, provider: AlbumProvider) -> None:
        """Create a sync service.

        Args:
            config: Configuration store for the sync interval.
            provider: Album provider that owns the photo files and status.

        """
        self._config = config
        self._provider = provider
        self._stop_event = threading.Event()
        self._trigger_event = threading.Event()
        self._interval_s = config.sync.interval_minutes * 60
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._do_sync()
            self._interval_s = self._config.sync.interval_minutes * 60
            remaining = self._interval_s
            while remaining > 0 and not self._stop_event.is_set():
                wait_for = min(remaining, 60)
                if self._trigger_event.wait(timeout=wait_for):
                    self._trigger_event.clear()
                    break
                remaining -= wait_for

    def _do_sync(self) -> None:
        try:
            self._provider.sync()
        except Exception as exc:
            logging.error("SyncService: provider sync failed: %s", exc)
        try:
            if types.EVT_SYNC_COMPLETE is not None:
                pygame.event.post(pygame.event.Event(types.EVT_SYNC_COMPLETE))
        except Exception as post_exc:
            logging.warning("EVT_SYNC_COMPLETE post failed: %s", post_exc)

    def trigger(self) -> None:
        """Trigger an immediate sync."""
        self._trigger_event.set()

    def stop(self) -> None:
        """Stop the sync service thread and release the provider.

        Blocks: joins the worker thread (up to 5 s) and then closes the
        provider, which waits up to 60 s for an in-flight sync to finish.
        """
        self._stop_event.set()
        self._trigger_event.set()
        self._thread.join(timeout=5.0)
        self._provider.close()

    @property
    def provider(self) -> AlbumProvider:
        """The album provider this service syncs."""
        return self._provider

    @property
    def status(self) -> SyncStatus:
        """Current sync status, as a defensive copy from the provider."""
        return self._provider.status()
