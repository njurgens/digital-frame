"""Google Photos provider stub: satisfies the contract, not yet implemented."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from piframe.album import Album
from piframe.providers.base import BaseAlbumProvider

if TYPE_CHECKING:
    from piframe.config_store import ConfigStore


class GooglePhotosConfig:
    """Google Photos provider settings (reserved; no keys yet)."""

    def __init__(self, config: ConfigStore) -> None:
        """Wrap the config store (no keys are read yet)."""
        self._config = config


class GooglePhotosProvider(BaseAlbumProvider):
    """Placeholder provider for the future Google Photos source.

    ``sync`` returns an empty album and reports a not-yet-implemented
    status instead of raising, so the slideshow keeps running with an
    empty collection (FR-5).

    For configuration and how to add a new provider, see
    ``docs/album-providers.md``.
    """

    def __init__(self, config: GooglePhotosConfig) -> None:
        """Create the stub with its (currently empty) config wrapper."""
        super().__init__()
        self._config = config

    @property
    def storage_dir(self) -> Path | None:
        """The stub stores no files locally."""
        return None

    def _do_sync(self) -> Album:
        self._note_error("Google Photos provider is not yet implemented")
        return Album()
