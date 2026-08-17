> **Superseded:** this task doc predates the final design; its references and details may not match the shipped code — see `DESIGN.md` and `FEATURE.md`.

# T06: Implement `GooglePhotosProvider` stub and `GooglePhotosConfig`

## Description

Create a placeholder provider for Google Photos that satisfies `AlbumProvider` but raises `NotImplementedError` on `sync()`.

## References

- [DESIGN.md §3.4](DESIGN.md#34-srcpiframeprovidersgooglepy)

## Write tests

**File:** `tests/test_providers.py` (add to existing file)

```python
def test_google_sync_raises():
    """sync() raises NotImplementedError."""


def test_google_status_has_error():
    """status() returns SyncStatus with last_error set."""


def test_google_stop_noop():
    """stop() does nothing."""


def test_google_config_instantiates():
    """GooglePhotosConfig(config) creates without error."""
```

Run: `bash eng/test.sh --skip-diff -k "test_google_"` — tests should fail (module doesn't exist yet).

## Implement

**New file:** `src/piframe/providers/google.py`
- `GooglePhotosConfig` — wraps `ConfigStore` (no properties yet)
- `GooglePhotosProvider` — `sync()` raises `NotImplementedError`, `status()` returns `last_error`, `stop()` no-op

**Modified:** `src/piframe/providers/__init__.py` — add `GooglePhotosConfig`, `GooglePhotosProvider` to `__all__`

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_google_"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T06: Implement `GooglePhotosProvider` stub and `GooglePhotosConfig`"
```
