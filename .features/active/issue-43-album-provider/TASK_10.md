# T10: Remove `framesync/` directory and update `eng/install.sh`

## Description

Remove the `framesync/` directory (all files) since the sync logic is now in `OneDriveProvider`. Update `eng/install.sh` to remove references to framesync deployment.

## References

- [DESIGN.md §3.2](DESIGN.md#32-srcpiframeprovidersonedrivepy) — framesync/ removal
- [DESIGN.md §5.1](DESIGN.md#51-existing-onedrive-users) — config migration

## Write tests

No new tests needed. This is a cleanup task — existing tests should still pass after removal.

## Implement

**Relocated:** `framesync/framesync-wifi.sudoers` → `etc/sudoers.d/framesync-wifi` (new `etc/` directory at repo root). The sudoers file is still needed by `WifiManager` for `sudo nmcli` commands.

**Deleted:** `framesync/` directory (all files: `framesync.py`, `config.toml.example`, `framesync.service`, `framesync.timer`). The `framesync-wifi.sudoers` was moved to `etc/sudoers.d/` above.

**Modified:** `eng/install.sh`
- Update sudoers installation path from `${REMOTE_DIR}/framesync/framesync-wifi.sudoers` to `${REMOTE_DIR}/etc/sudoers.d/framesync-wifi`
- Remove `framesync.service` / `framesync.timer` deployment if referenced
- The rsync of the repo root already covers everything, so no special handling needed

**Updated docstrings:** Any remaining references to "framesync" in `sync_service.py`, `modules/sync.py`, or other source files should be updated to reference "provider" instead.

**Modified:** Any remaining files with stale "framesync" docstrings/comments (e.g., `sync_service.py`, `modules/sync.py`) — update to reference "provider" instead.

## Validate

```bash
# framesync/ should not exist
test ! -d framesync && echo "OK" || echo "FAIL: framesync/ still exists"

# sudoers file should exist at new location
test -f etc/sudoers.d/framesync-wifi && echo "OK" || echo "FAIL: sudoers file missing"

# All existing tests still pass
bash eng/test.sh --skip-diff
bash eng/check.sh
```
## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T10: Remove `framesync/` directory and update `eng/install.sh`"
```
