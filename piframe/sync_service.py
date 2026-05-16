from __future__ import annotations

import copy
import datetime
import logging
import sys
import threading
from pathlib import Path

import pygame

from piframe import types
from piframe.config_store import ConfigStore
from piframe.types import SyncStatus


class SyncService:
    def __init__(self, config: ConfigStore):
        self._config = config
        self._stop_event = threading.Event()
        self._trigger_event = threading.Event()
        self._status = SyncStatus()
        self._status_lock = threading.Lock()
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
        with self._status_lock:
            self._status.in_progress = True
            self._status.last_error = None
        try:
            framesync_dir = str(Path(__file__).parent.parent / "framesync")
            if framesync_dir not in sys.path:
                sys.path.insert(0, framesync_dir)
            from framesync import sync as framesync_sync

            cfg = self._config.sync
            share_url = cfg.share_url
            output_dir = Path(cfg.output_dir)
            if not share_url:
                logging.info("SyncService: no share_url configured, skipping sync")
                with self._status_lock:
                    self._status.in_progress = False
                return

            framesync_sync(cfg.share_url, cfg.password, cfg.output_dir)

            photo_count = sum(
                1
                for path in output_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}
            )
            with self._status_lock:
                self._status.last_sync_time = datetime.datetime.now()
                self._status.photo_count = photo_count
                self._status.in_progress = False
                self._status.last_error = None
            try:
                if types.EVT_SYNC_COMPLETE is not None:
                    pygame.event.post(pygame.event.Event(types.EVT_SYNC_COMPLETE))
            except Exception as exc:
                logging.warning("EVT_SYNC_COMPLETE post failed: %s", exc)
        except Exception as exc:
            with self._status_lock:
                self._status.in_progress = False
                self._status.last_error = str(exc)
            logging.error("SyncService error: %s", exc)

    def trigger(self) -> None:
        self._trigger_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._trigger_event.set()

    @property
    def status(self) -> SyncStatus:
        with self._status_lock:
            return copy.copy(self._status)
