"""Tests for SyncService with a mock provider (no network)."""

from __future__ import annotations

import os
import time
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import Any

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import pytest

import piframe.types as ptypes
from piframe.album import Album
from piframe.config_store import ConfigStore
from piframe.image import Image
from piframe.sync_service import SyncService
from piframe.types import SyncStatus, init_events

# Register custom event IDs at import time so the sync thread's first
# post (which happens as soon as the service thread starts) can find them.
init_events()


class MockProvider:
    """Configurable album provider double that records calls."""

    @property
    def storage_dir(self) -> Path | None:
        """The double stores no files."""
        return None

    def __init__(self) -> None:
        """Initialise call counters and an empty album/status."""
        self.sync_calls = 0
        self.closed = False
        self.fail: Exception | None = None
        self.paths: list[Path] = []
        self._album = Album()
        self._status = SyncStatus()

    def sync(self) -> Album:
        """Simulate a provider sync, optionally failing."""
        self.sync_calls += 1
        if self.fail is not None:
            self._status.in_progress = False
            self._status.last_error = str(self.fail)
            self._status.last_sync_time = datetime.now()
            raise self.fail
        self._album = Album.from_images([Image(p) for p in self.paths])
        self._status.in_progress = False
        self._status.photo_count = len(self.paths)
        self._status.last_sync_time = datetime.now()
        self._status.last_error = None
        return self._album

    def album(self) -> Album:
        """Return the last synced album."""
        return self._album

    def status(self) -> SyncStatus:
        """Return the current status object."""
        return self._status

    def close(self) -> None:
        """Record that the provider was closed."""
        self.closed = True


@pytest.fixture
def config(tmp_path: Path) -> ConfigStore:
    """Config store with a long sync interval."""
    p = tmp_path / "config.toml"
    p.write_text("[sync]\ninterval_minutes = 1440\n")
    return ConfigStore(p)


@pytest.fixture
def mock_provider() -> MockProvider:
    """The mock album provider shared by the service fixture."""
    return MockProvider()


@pytest.fixture
def service(config: ConfigStore, mock_provider: MockProvider) -> Generator[SyncService]:
    """Sync service wired to the mock provider; stopped on teardown."""
    svc = SyncService(config, provider=mock_provider)
    yield svc
    svc.stop()


def _wait_for(predicate: Any, timeout: float = 5.0) -> bool:
    """Poll *predicate* until it returns true or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def _drain_for_event() -> pygame.event.Event | None:
    """Return the next EVT_SYNC_COMPLETE event from the pygame queue, if any."""
    for event in pygame.event.get():
        if event.type == ptypes.EVT_SYNC_COMPLETE:
            return event
    return None


def test_sync_service_calls_provider_on_start(
    service: SyncService, mock_provider: MockProvider
) -> None:
    """The service runs the provider's sync as soon as its thread starts."""
    assert _wait_for(lambda: mock_provider.sync_calls >= 1)


def test_sync_service_status_delegates_to_provider(
    service: SyncService, mock_provider: MockProvider
) -> None:
    """Status returns the provider's status (photo count included)."""
    mock_provider.paths = [Path("/photos/a.jpg"), Path("/photos/b.jpg")]
    service.trigger()
    assert _wait_for(lambda: mock_provider.sync_calls >= 2)
    status = service.status
    assert status.photo_count == 2
    assert status.last_error is None
    assert status.in_progress is False


def test_sync_service_catches_provider_error_and_keeps_running(
    config: ConfigStore,
) -> None:
    """A failing provider does not kill the service; the error is in status."""
    provider = MockProvider()
    provider.fail = RuntimeError("boom")
    svc = SyncService(config, provider=provider)
    try:
        assert _wait_for(lambda: provider.sync_calls >= 1)
        assert _wait_for(lambda: provider.status().last_error == "boom")

        # The service recovers: clear the failure and trigger another sync.
        provider.fail = None
        svc.trigger()
        assert _wait_for(lambda: provider.sync_calls >= 2)
        assert provider.status().last_error is None
    finally:
        svc.stop()


def test_sync_service_posts_sync_complete_event(
    service: SyncService, mock_provider: MockProvider
) -> None:
    """Each sync posts an EVT_SYNC_COMPLETE event to the pygame queue.

    Drains the global pygame event queue before the assertion so a stale
    event from another test cannot fake a pass.
    """
    assert _wait_for(lambda: mock_provider.sync_calls >= 1)
    # Clear any stale events, then trigger a fresh sync.
    _drain_for_event()
    service.trigger()
    assert _wait_for(lambda: mock_provider.sync_calls >= 2)
    assert _wait_for(lambda: _drain_for_event() is not None)


def test_sync_service_posts_event_after_failed_sync(
    config: ConfigStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """EVT_SYNC_COMPLETE is posted even when the provider sync fails."""
    provider = MockProvider()
    provider.fail = RuntimeError("boom")
    svc = SyncService(config, provider=provider)
    try:
        assert _wait_for(lambda: provider.sync_calls >= 1)
        assert _wait_for(lambda: _drain_for_event() is not None)
    finally:
        svc.stop()


def test_sync_service_survives_event_post_failure(
    config: ConfigStore, mock_provider: MockProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failing event post is logged, not raised, out of the sync loop."""

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("post failed")

    monkeypatch.setattr(pygame.event, "post", _boom)
    svc = SyncService(config, provider=mock_provider)
    try:
        assert _wait_for(lambda: mock_provider.sync_calls >= 1)
        svc.trigger()
        assert _wait_for(lambda: mock_provider.sync_calls >= 2)
    finally:
        svc.stop()


def test_sync_service_trigger_runs_sync_immediately(
    service: SyncService, mock_provider: MockProvider
) -> None:
    """trigger() wakes the wait loop and runs a sync well before the interval."""
    assert _wait_for(lambda: mock_provider.sync_calls >= 1)
    service.trigger()
    assert _wait_for(lambda: mock_provider.sync_calls >= 2, timeout=3.0)


def test_sync_service_stop_closes_provider(
    service: SyncService, mock_provider: MockProvider
) -> None:
    """stop() halts the thread and closes the provider."""
    assert _wait_for(lambda: mock_provider.sync_calls >= 1)
    service.stop()  # stop() joins the worker thread, so this is deterministic
    assert mock_provider.closed
    assert mock_provider.sync_calls == 1  # no further syncs after stop
