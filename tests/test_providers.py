"""Unit tests for the providers package."""

from __future__ import annotations

import pytest


def test_provider_name_from_string_local() -> None:
    """from_string('local') returns ProviderName.LOCAL."""
    from piframe.providers import ProviderName

    assert ProviderName.from_string("local") is ProviderName.LOCAL


def test_provider_name_from_string_onedrive() -> None:
    """from_string('onedrive') returns ProviderName.ONEDRIVE."""
    from piframe.providers import ProviderName

    assert ProviderName.from_string("onedrive") is ProviderName.ONEDRIVE


def test_provider_name_from_string_google() -> None:
    """from_string('google') returns ProviderName.GOOGLE."""
    from piframe.providers import ProviderName

    assert ProviderName.from_string("google") is ProviderName.GOOGLE


def test_provider_name_from_string_unknown_raises() -> None:
    """from_string('unknown') raises ValueError with valid options in message."""
    from piframe.providers import ProviderName

    with pytest.raises(ValueError, match="Unknown sync provider"):
        ProviderName.from_string("unknown")


def test_album_provider_protocol_importable() -> None:
    """AlbumProvider is importable from piframe.providers."""
    from piframe.providers import AlbumProvider

    assert AlbumProvider is not None
