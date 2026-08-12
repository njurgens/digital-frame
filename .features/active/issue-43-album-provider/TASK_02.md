# T02: Fix `album_provider.py` — rename to `DirectoryReader`, drop broken import

## Description

`src/piframe/album_provider.py` imports `AlbumProvider` from `piframe.types`, but that class doesn't exist. The class `DirectoryAlbumProvider` also collides with the new `AlbumProvider` protocol name.

## References

- [DESIGN.md §3.9](DESIGN.md#39-srcpiframealbum_providery-renamed--fixed) — rename + import fix

## Write tests

**File:** `tests/test_providers.py` (add to existing file from T01)

```python
def test_directory_reader_import():
    """DirectoryReader is importable from piframe.album_provider."""


def test_directory_reader_nonexistent_dir(tmp_path):
    """get_album() returns [] for nonexistent directory."""


def test_directory_reader_scans_files(tmp_path):
    """get_album() returns sorted list of image files."""
    # Create test .jpg, .png files in tmp_path
    # Verify they appear sorted in result


def test_directory_reader_ignores_non_image(tmp_path):
    """get_album() ignores files with non-image extensions."""
    # Create .txt, .pdf files alongside image files
    # Verify only image files appear in result
```

Run: `bash eng/test.sh --skip-diff -k "test_directory_reader"` — tests should fail (broken import).

## Implement

**Modified:** `src/piframe/album_provider.py`
- Remove `from piframe.types import AlbumProvider` (broken import)
- Rename `DirectoryAlbumProvider` → `DirectoryReader`
- Remove `AlbumProvider` base class (standalone class, no inheritance)

Note: `DirectoryAlbumProvider` is not imported anywhere in the codebase (slideshow_player.py does inline scanning), so no downstream references need updating.

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_directory_reader"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T02: Fix `album_provider.py` — rename to `DirectoryReader`, drop broken import"
```
