# T05: Implement `LocalProvider` and `LocalConfig`

## Description

Implement a provider that reads images from a local directory.

## References

- [DESIGN.md §3.3](DESIGN.md#33-srcpiframeproviderslocalpy)

## Write tests

**File:** `tests/test_providers.py` (add to existing file)

```python
def test_local_config_reads_source_dir(tmp_path):
    """LocalConfig reads source_dir from [sync.local]."""


def test_local_sync_same_dir(tmp_path):
    """source_dir == output_dir: no copies, just scan."""


def test_local_sync_copies_new_files(tmp_path):
    """New files in source are copied to output."""


def test_local_sync_destructive_cleanup(tmp_path):
    """Files in output not in source are deleted."""


def test_local_sync_empty_source():
    """Missing source dir returns empty list."""


def test_local_status():
    """status() returns correct photo count."""


def test_local_stop_noop():
    """stop() does nothing."""
```

Run: `bash eng/test.sh --skip-diff -k "test_local_"` — tests should fail (module doesn't exist yet).

## Implement

**New file:** `src/piframe/providers/local.py`
- `LocalConfig` — wraps `ConfigStore`, reads `source_dir` from `[sync.local]` via `_read_nested()`
- `LocalProvider` — scan/copy from `source_dir` to `output_dir` with destructive cleanup
- When `source_dir` is empty or missing, scan `output_dir` directly (no copy)

**Modified:** `src/piframe/providers/__init__.py` — add `LocalConfig`, `LocalProvider` to `__all__`

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_local_"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T05: Implement `LocalProvider` and `LocalConfig`"
```
