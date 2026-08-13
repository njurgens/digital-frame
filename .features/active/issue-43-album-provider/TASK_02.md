# T02: Fix `album_provider.py` — rename to `DirectoryReader`, drop broken import

## Description

Verify `src/piframe/album_provider.py` uses `DirectoryReader` (not `DirectoryAlbumProvider`) with no broken import. (Already implemented — verify and add tests.)

## References

- [DESIGN.md §3.9](DESIGN.md#39-srcpiframealbum_providery-renamed--fixed) — rename + import fix

## Write tests

**File:** `tests/test_providers.py` (add to existing file from T01)

Tests should pass immediately (code already exists).

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

Run: `bash eng/test.sh --skip-diff -k "test_directory_reader"` — tests should pass (code already exists).

## Implement

No code changes needed. Verify existing implementation matches DESIGN.md §3.9.

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
