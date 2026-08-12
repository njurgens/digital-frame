# T07: Refactor `SyncService` to accept `AlbumProvider`

## Description

Refactor `SyncService` to accept an `AlbumProvider` in its constructor instead of importing `framesync` directly.

## References

- [DESIGN.md §3.6](DESIGN.md#36-srcpiframesync_servicepy-modified)

## Write tests

**File:** `tests/test_modules.py` (add to existing test file)

```python
def test_sync_service_delegates_to_provider(mocker):
    """SyncService._do_sync() calls provider.sync() with correct output_dir."""


def test_sync_service_posts_event_on_success(mocker):
    """EVT_SYNC_COMPLETE is posted after successful sync."""


def test_sync_service_catches_provider_error(mocker):
    """Exception from provider is caught, last_error is set."""


def test_sync_service_stop_calls_provider_stop(mocker):
    """stop() calls provider.stop()."""
```

Run: `bash eng/test.sh --skip-diff -k "test_sync_service_"` — tests should fail (constructor signature changed).

## Implement

**Modified:** `src/piframe/sync_service.py`
- Constructor takes `provider: AlbumProvider, config: ConfigStore` (two args instead of one)
- `_do_sync()` calls `self._provider.sync(output_dir)` and `self._provider.status()`
- `stop()` calls `self._provider.stop()`
- Remove all `framesync` imports and `sys.path` manipulation
- Remove `share_url`/`password` checks (provider handles that)

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_sync_service_"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T07: Refactor `SyncService` to accept `AlbumProvider`"
```
