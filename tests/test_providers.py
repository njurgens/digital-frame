"""Unit tests for the providers package."""

from __future__ import annotations

from pathlib import Path

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


def test_directory_reader_import() -> None:
    """DirectoryReader is importable from piframe.album_provider."""
    from piframe.album_provider import DirectoryReader

    assert DirectoryReader is not None


def test_directory_reader_nonexistent_dir(tmp_path: Path) -> None:
    """get_album() returns [] for nonexistent directory."""
    from piframe.album_provider import DirectoryReader

    reader = DirectoryReader(tmp_path / "does-not-exist")
    assert reader.get_album() == []


def test_directory_reader_scans_files(tmp_path: Path) -> None:
    """get_album() returns sorted list of image files."""
    from piframe.album_provider import DirectoryReader

    (tmp_path / "b.png").touch()
    (tmp_path / "a.jpg").touch()
    (tmp_path / "c.jpeg").touch()
    (tmp_path / "d.gif").touch()

    reader = DirectoryReader(tmp_path)
    result = reader.get_album()

    assert len(result) == 4
    names = [p.name for p in result]
    assert names == ["a.jpg", "b.png", "c.jpeg", "d.gif"]


def test_directory_reader_ignores_non_image(tmp_path: Path) -> None:
    """get_album() ignores files with non-image extensions."""
    from piframe.album_provider import DirectoryReader

    (tmp_path / "photo.jpg").touch()
    (tmp_path / "notes.txt").touch()
    (tmp_path / "report.pdf").touch()
    (tmp_path / "image.png").touch()

    reader = DirectoryReader(tmp_path)
    result = reader.get_album()

    assert len(result) == 2
    names = [p.name for p in result]
    assert names == ["image.png", "photo.jpg"]
