"""Album provider abstractions and provider registry."""

from __future__ import annotations

from enum import StrEnum

from piframe.providers.album_provider import AlbumProvider


class ProviderName(StrEnum):
    """Supported album provider names."""

    ONEDRIVE = "onedrive"
    LOCAL = "local"
    GOOGLE = "google"

    @classmethod
    def from_string(cls, value: str) -> ProviderName:
        """Parse a provider name string, raising on unknown values."""
        try:
            return cls(value)
        except ValueError:
            valid = ", ".join(repr(m.value) for m in cls)
            raise ValueError(f"Unknown sync provider '{value}'. Valid: {valid}") from None


__all__ = [
    "AlbumProvider",
    "ProviderName",
]
