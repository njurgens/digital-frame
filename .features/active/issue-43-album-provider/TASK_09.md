# T09: Update `SettingsPanel` / `SettingsModule` for new `SyncService` constructor

## Description

`SettingsPanel` imports `SyncService` as a type hint. `SettingsModule` may construct `SyncService` directly. Verify no code constructs `SyncService(config)` outside of `SyncModule`.

## References

- [DESIGN.md §3.6](DESIGN.md#36-srcpiframesync_servicepy-modified) — constructor signature change

## Write tests

No new tests needed. This is an audit task — verify existing tests still pass after the constructor change.

## Implement

**Audit:** Search for direct `SyncService(` construction:
```bash
grep -rn "SyncService(" src/piframe/ --include="*.py" | grep -v "class SyncService\|DimModule\|sync_service: SyncService\|modules/sync.py"
```

If any direct construction is found outside `SyncModule`, update it to use `SyncModule` instead or the new two-arg constructor.

## Validate

```bash
# Should return empty or only SyncModule reference
grep -rn "SyncService(" src/piframe/ --include="*.py" | grep -v "class SyncService\|DimModule\|sync_service: SyncService\|modules/sync.py"
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T09: Update `SettingsPanel` / `SettingsModule` for new `SyncService` constructor"
```
