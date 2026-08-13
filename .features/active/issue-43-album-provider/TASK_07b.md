# T07b: Remove deprecated `share_url`/`password` from `ConfigStore`

## Description

Remove the deprecated `share_url` and `password` properties from `ConfigStore` now that `SyncService` uses `AlbumProvider`. This is a cleanup task with no behavioral change.

## References

- [DESIGN.md §3.8](DESIGN.md#38-srcpiframeconfig_storepy-modified)

## Write tests

No new tests needed. This is a cleanup — existing tests should still pass.

## Implement

**Modified:** `src/piframe/config_store.py`
- Remove `share_url` and `password` properties from `_SyncCfg` (deprecated in T03, no longer used)
- Remove `share_url` and `password` from `_DEFAULTS["sync"]` (retain nested `sync.onedrive.share_url`/`password`)
- Remove `("sync", "share_url")` and `("sync", "password")` from `_PROTECTED` (retain `("sync", "provider")`)

## Validate

```bash
bash eng/test.sh --skip-diff
bash eng/check.sh
```

## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T07b: remove deprecated share_url/password from ConfigStore"
```