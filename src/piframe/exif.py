"""EXIF metadata for photos: a value object and its file loader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image as PilImage

#: Files larger than this are not parsed for EXIF: image decoders are a
#: crash-class risk on crafted input, and a photo this large is not one the
#: frame will display anyway.
_MAX_EXIF_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Exif:
    """Read-only EXIF metadata for a single image.

    Attributes:
        datetime: Capture time, or None when the image carries no usable
            capture timestamp.
        orientation: EXIF orientation tag (1 = normal).

    """

    datetime: datetime | None = None
    orientation: int = 1


def load_exif(path: Path) -> Exif | None:
    """Read capture datetime and orientation from an image file's EXIF data.

    Returns None when the file cannot be read, is too large to parse, or
    carries no usable EXIF data.  Never raises: EXIF is optional metadata
    and its absence must not block slideshow operation.
    """
    try:
        if path.stat().st_size > _MAX_EXIF_BYTES:
            return None
        with PilImage.open(path) as img:
            raw = img.getexif()
            # DateTimeOriginal (0x9003) lives in the Exif sub-IFD, not in
            # the base IFD that getexif() returns; fall back to the base
            # IFD's DateTime (0x0132) for files that only carry that tag.
            sub_ifd = raw.get_ifd(0x8769)
            orientation = int(raw.get(0x0112) or 1)
            stamp = sub_ifd.get(0x9003) or raw.get(0x0132)
            capture: datetime | None = None
            if stamp:
                try:
                    capture = datetime.strptime(str(stamp).strip(), "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    capture = None
            return Exif(datetime=capture, orientation=orientation)
    except Exception:
        return None
