# T04: Implement `OneDriveProvider` and `OneDriveConfig`

## Description

Extract the existing OneDrive sync logic from `framesync/framesync.py` into `OneDriveProvider`.

## References

- [DESIGN.md §3.2](DESIGN.md#32-srcpiframeprovidersonedrivepy)

## Write tests

**File:** `tests/test_providers.py` (add to existing file)

```python
def test_onedrive_config_reads_share_url(tmp_path):
    """OneDriveConfig reads share_url from [sync.onedrive]."""
    # Write TOML with [sync.onedrive] share_url = "https://test"


def test_onedrive_config_reads_password(tmp_path):
    """OneDriveConfig reads password from [sync.onedrive]."""


def test_onedrive_provider_satisfies_protocol():
    """OneDriveProvider has sync, status, stop methods."""
    # Structural check — callable attributes exist


def test_onedrive_status_initial():
    """New provider has default SyncStatus."""


def test_onedrive_stop_sets_event():
    """stop() sets internal stop event."""


def test_onedrive_sync_happy_path(mocker):
    """Full sync flow: token → validate → redeem → sync folder."""
    # Mock all requests.post/get calls
    # Verify files downloaded to output_dir


def test_onedrive_sync_destructive_cleanup(mocker, tmp_path):
    """Local file not in remote listing is deleted."""


def test_onedrive_sync_single_file(mocker, tmp_path):
    """Share points to a single file (not folder)."""


def test_onedrive_status_after_sync(mocker):
    """status() returns correct photo_count and last_sync_time after sync."""
```

Run: `bash eng/test.sh --skip-diff -k "test_onedrive"` — tests should fail (module doesn't exist yet).

## Implement

**New file:** `src/piframe/providers/onedrive.py`
- `OneDriveConfig` — wraps `ConfigStore`, reads `share_url` / `password` from `[sync.onedrive]` via `_read_nested()`
- `OneDriveProvider` — extract all functions from `framesync/framesync.py` as private instance methods
- **Important:** The existing `framesync.sync()` returns `None`. The `AlbumProvider` protocol requires `sync(output_dir: Path) -> list[Path]`. Modify the extracted logic to collect and return the list of newly created files.
- **Important:** the existing `framesync.sync()` returns `None`; `AlbumProvider.sync()` must return `list[Path]`. Track newly created files and return them.
- Sync flow: `_get_badger_token()` → `_encode_url()` → `_validate_password()` → `_redeem_share()` → `_sync_folder()` or single file download
- `status()` returns `SyncStatus` with `photo_count` from scanning `output_dir`
- `stop()` sets `threading.Event` checked between page fetches

**Modified:** `src/piframe/providers/__init__.py` — add `OneDriveConfig`, `OneDriveProvider` to `__all__`

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_onedrive"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T04: Implement `OneDriveProvider` and `OneDriveConfig`"
```
