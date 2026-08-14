# Add Additional EXIF Tags to Image Metadata

## Context

`Image.exif` currently exposes only the essential tags needed for slideshow rendering:
- `datetime` — date/time photo was taken
- `orientation` — EXIF orientation tag for correct display

Additional EXIF tags are available in most photos and would be useful for future features like photo info overlays, location-based filtering, and camera metadata display.

## Proposed Tags

| Tag | Pillow Enum | Type | Use Case |
|-----|-------------|------|----------|
| `make` | `ExifTags.Base.Make` | `str \| None` | Camera manufacturer |
| `model` | `ExifTags.Base.Model` | `str \| None` | Camera model |
| `f_number` | `ExifTags.ExifIFD.FNumber` | `float \| None` | Aperture (e.g. `2.8`) |
| `exposure_time` | `ExifTags.ExifIFD.ExposureTime` | `tuple[int, int] \| None` | Shutter speed as `(numerator, denominator)`, e.g. `(1, 1000)` for 1/1000s |
| `iso_speed` | `ExifTags.ExifIFD.ISOSpeedRatings` | `int \| None` | ISO setting |
| `focal_length` | `ExifTags.ExifIFD.FocalLength` | `float \| None` | Focal length (mm) |
| `gps_latitude` | `ExifTags.GPS.GPSLatitude` + `GPSLatitudeRef` | `float \| None` | Decimal degrees (negative = south) |
| `gps_longitude` | `ExifTags.GPS.GPSLongitude` + `GPSLongitudeRef` | `float \| None` | Decimal degrees (negative = west) |
| `flash` | `ExifTags.ExifIFD.Flash` | `int \| None` | Flash firing status |

### Design Notes (to be resolved during implementation)

- **IFD grouping**: Tags span multiple IFDs — Base (`make`, `model`), ExifIFD (`f_number`, `exposure_time`, `iso_speed`, `focal_length`, `flash`), GPS (`gps_latitude`, `gps_longitude`). The implementer must use `exif.get_ifd(IFD.Exif)` and `exif.get_ifd(IFD.GPS)` to access the correct directories.
- **Error handling**: Strategy for corrupt/incomplete EXIF blocks (`getexif()` raising) to be specified during design.
- **GPS rational-to-decimal**: Implementer must convert `(degrees, minutes, seconds)` rational tuples plus `GPSLatitudeRef`/`GPSLongitudeRef` to signed decimal degrees.

## Design

- All additional tags follow the same lazy-loading pattern as `datetime`/`orientation`.
- The `Exif` class reads all available tags in a single `PIL.Image.getexif()` call — no extra file I/O.
- Tags that are absent from the file return `None`.
- GPS rational values (stored as `(numerator, denominator)` tuples in EXIF) are converted to decimal degrees.

## Scope

- In scope: Extend `Exif` dataclass with new properties; update lazy-loading to parse all tags in one pass.
- Out of scope: UI elements to display metadata (future issue).

## Acceptance Criteria

1. `Image.exif` exposes the new properties alongside `datetime` and `orientation`.
2. Missing tags return `None` (no exceptions).
3. GPS rational-to-decimal conversion is correct for all quadrants.
4. No additional file reads — all tags extracted from the single `getexif()` call.
5. `eng/test.sh` passes with new unit tests for tag parsing.