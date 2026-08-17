"""Album provider abstractions and concrete providers."""

from __future__ import annotations

from piframe.providers.album_provider import AlbumProvider
from piframe.providers.base import BaseAlbumProvider
from piframe.providers.google import GooglePhotosConfig, GooglePhotosProvider
from piframe.providers.local import LocalConfig, LocalProvider
from piframe.providers.onedrive import OneDriveConfig, OneDriveProvider
from piframe.providers.provider_name import ProviderName

__all__ = [
    "AlbumProvider",
    "BaseAlbumProvider",
    "GooglePhotosConfig",
    "GooglePhotosProvider",
    "LocalConfig",
    "LocalProvider",
    "OneDriveConfig",
    "OneDriveProvider",
    "ProviderName",
]
