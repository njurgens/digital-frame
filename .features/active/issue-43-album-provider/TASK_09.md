# T09: Update `_write_toml()` to handle nested dicts

## Description

The existing `_write_toml()` writes flat key-value pairs per section. It needs to detect nested dicts and emit `[section.subsection]` headers for provider-specific sub-sections.

## References

- [DESIGN.md §3.8](DESIGN.md#38-srcpiframeconfig_storepy-modified) — `_write_toml()` modification

## Write tests

**File:** `tests/test_config_store.py` (add to existing file)

```python
def test_write_toml_nested_section(tmp_path):
    """_write_toml() emits [sync.onedrive] header for nested dict values."""
    # Set cfg._data['sync']['onedrive'] = {'share_url': '...', 'password': '...'}
    # Flush and verify [sync.onedrive] appears in output


def test_write_toml_flat_values(tmp_path):
    """_write_toml() still writes flat key-value pairs for non-dict values."""
```

Run: `bash eng/test.sh --skip-diff -k "test_write_toml"` — tests should fail (nested handling not implemented yet).

## Implement

**Modified:** `src/piframe/config_store.py`
- In `_write_toml()`, when a value is a `dict`, recurse and write a `[section.subsection]` header instead of a flat key-value line
- Keep existing handling for `bool`, `float`, `int`, `str` leaf values
- **Note on `flush_now()`:** After this change, `flush_now()` reads the disk TOML and restores protected keys. Verify that nested protected keys (e.g., `sync.onedrive.share_url`) survive a flush cycle correctly. If not, update `flush_now()` to handle nested paths.

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_write_toml"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T09: Update `_write_toml()` to handle nested dicts"
```
