# Migrate PhotoCache to ImageOps.exif_transpose()

## Context

`PhotoCache._apply_exif_orientation()` manually reads the EXIF orientation tag via `img._getexif()` (a deprecated private method) and applies a hardcoded switch for orientations 1–8.

Pillow provides `ImageOps.exif_transpose()` which:
- Uses the public `getexif()` API
- Handles orientation lookup and transposition in one call
- Strips the orientation tag after applying it (prevents double-rotation downstream)
- Handles edge cases the manual implementation may miss

## Design

Replace `_apply_exif_orientation()` in `PhotoCache._render()` with:

```python
from PIL import ImageOps

img = Image.open(path)
img = ImageOps.exif_transpose(img)
img = img.convert("RGB")
```

The `Exif.orientation` property on `Image` remains available for consumers that need the raw value (e.g., metadata display).

## Scope

- In scope: Update `PhotoCache._render()` to use `ImageOps.exif_transpose()`. Remove `_apply_exif_orientation()` method.
- Out of scope: Any changes to `Image.exif` or `Exif` classes.

## Acceptance Criteria

1. `PhotoCache._render()` uses `ImageOps.exif_transpose()` instead of manual orientation handling.
2. `_apply_exif_orientation()` method removed.
3. All existing tests pass (images with various orientations render correctly).
4. `eng/check.sh` passes with no type errors.