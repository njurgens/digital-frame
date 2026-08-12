# T03: Add `provider` property and `_read_nested()` to `ConfigStore`

## Description

Update `ConfigStore` to support the new provider-based config structure.

## References

- [DESIGN.md §3.8](DESIGN.md#38-srcpiframeconfig_storepy-modified)

## Write tests

**File:** `tests/test_config_store.py` (add to existing file)

```python
def test_sync_provider_default(tmp_path):
    """Default provider is LOCAL when no config file exists."""


def test_sync_provider_from_file(tmp_path):
    """provider = 'onedrive' in TOML is read as ProviderName.ONEDRIVE."""
    # Write TOML with [sync] provider = "onedrive"


def test_sync_provider_protected(tmp_path):
    """provider is in _PROTECTED set (cannot be overwritten by flush)."""


def test_read_nested_success(tmp_path):
    """_read_nested('sync', 'onedrive', 'share_url') returns correct value."""
    # Write TOML with [sync.onedrive] share_url = "..."


def test_read_nested_missing(tmp_path):
    """_read_nested() with missing keys returns the default."""


def test_sync_no_share_url_password():
    """_SyncCfg has no share_url or password attributes."""
```

Run: `bash eng/test.sh --skip-diff -k "test_sync_provider or test_read_nested or test_sync_no_share"` — tests should fail.

## Implement

**Modified:** `src/piframe/config_store.py`
1. Add `from piframe.providers import ProviderName` import
2. `_SyncCfg`: add `provider` property (returns `ProviderName`, validated via `from_string()`)
3. `_SyncCfg`: remove `share_url` and `password` properties
4. `_DEFAULTS["sync"]`: add `provider = "local"`, remove `share_url` and `password`
5. `_PROTECTED`: add `("sync", "provider")`, remove `("sync", "share_url")` and `("sync", "password")`
6. `ConfigStore`: add `_read_nested(*keys, default=...)` protected method

## Validate

```bash
bash eng/test.sh --skip-diff -k "test_sync_provider or test_read_nested or test_sync_no_share"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T03: Add `provider` property and `_read_nested()` to `ConfigStore`"
```
