# Migrate PhotoCache to ImageOps.exif_transpose()

## Problem

`PhotoCache._apply_exif_orientation()` uses `img._getexif()` — a private, deprecated Pillow method that reads raw numeric tag `274` directly. It manually switches on orientation values 2-8 and applies `Image.Transpose.*` operations.

Pillow provides `ImageOps.exif_transpose()` which:
- Uses the public `getexif()` API with `ExifTags.Base.Orientation` enum
- Handles the same orientation values plus edge cases
- Strips the orientation tag after applying the transposition (prevents double-rotation by downstream consumers)
- Optionally works in-place

## Change

Replace the manual orientation handling in `PhotoCache._render()`:

```python
# Before
img = Image.open(path)
img = self._apply_exif_orientation(img)  # manual switch on _getexif().get(274)
img = img.convert("RGB")

# After
from PIL import ImageOps
img = Image.open(path)
img = ImageOps.exif_transpose(img)
img = img.convert("RGB")
```

Remove `_apply_exif_orientation()` method entirely.

## Scope

- Modify `src/piframe/photo_cache.py` only
- No new dependencies (PIL/Pillow is already a dependency)
- No config or API changes

## Exit Criteria

1. `_apply_exif_orientation()` removed from `PhotoCache`
2. `ImageOps.exif_transpose()` used in `_render()`
3. All existing tests pass
4. `eng/check.sh` passes
5. Visual verification: images with EXIF orientation tags render correctly (no upside-down/sideways photos)