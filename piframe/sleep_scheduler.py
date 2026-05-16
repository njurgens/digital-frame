from __future__ import annotations

import datetime
import logging
import threading
import time

import pygame

from piframe.config_store import ConfigStore
from piframe import types


def is_sleep_time(now: datetime.time, sleep_t: datetime.time, wake_t: datetime.time) -> bool:
    now_m = now.hour * 60 + now.minute
    sleep_m = sleep_t.hour * 60 + sleep_t.minute
    wake_m = wake_t.hour * 60 + wake_t.minute
    if sleep_m == wake_m:
        return False
    if sleep_m < wake_m:
        return sleep_m <= now_m < wake_m
    return now_m >= sleep_m or now_m < wake_m


class SleepScheduler:
    def __init__(self, config: ConfigStore):
        self._config = config
        self._stop_event = threading.Event()
        self._kick_event = threading.Event()
        self._sleeping = False
        self._grace_until: float = 0.0
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            cfg = self._config.sleep
            now_t = datetime.datetime.now().time()
            in_grace = time.monotonic() < self._grace_until

            if not cfg.enabled or in_grace:
                if self._sleeping:
                    self._sleeping = False
                    try:
                        if types.EVT_WAKE is not None:
                            pygame.event.post(pygame.event.Event(types.EVT_WAKE))
                    except Exception as e:
                        logging.warning("EVT_WAKE post failed: %s", e)
            else:
                should_sleep = is_sleep_time(now_t, cfg.sleep_time_parsed, cfg.wake_time_parsed)
                if should_sleep and not self._sleeping:
                    self._sleeping = True
                    try:
                        if types.EVT_SLEEP is not None:
                            pygame.event.post(pygame.event.Event(types.EVT_SLEEP))
                    except Exception as e:
                        logging.warning("EVT_SLEEP post failed: %s", e)
                elif not should_sleep and self._sleeping:
                    self._sleeping = False
                    try:
                        if types.EVT_WAKE is not None:
                            pygame.event.post(pygame.event.Event(types.EVT_WAKE))
                    except Exception as e:
                        logging.warning("EVT_WAKE post failed: %s", e)

            self._kick_event.wait(timeout=30)
            self._kick_event.clear()

    def set_grace(self, until: float) -> None:
        self._grace_until = until

    def kick(self) -> None:
        """Interrupt the sleep-check wait and re-evaluate immediately."""
        self._kick_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._kick_event.set()
