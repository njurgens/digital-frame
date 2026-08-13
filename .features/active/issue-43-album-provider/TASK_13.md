# T13: Ensure all existing tests pass and `eng/check.sh` is clean

## Description

Final regression pass. Ensure all existing tests pass with zero failures and `eng/check.sh` reports zero lint/format/type errors.

## References

- [FEATURE.md Exit Criteria 8-10](FEATURE.md#exit-criteria)

## Write tests

No new tests. This is the final regression pass.

## Validate

```bash
# All tests pass
bash eng/test.sh

# Linter, formatter, type checker are clean
bash eng/check.sh

# All provider imports work
python -c "from piframe.providers import AlbumProvider, ProviderName, OneDriveConfig, OneDriveProvider, LocalConfig, LocalProvider, GooglePhotosConfig, GooglePhotosProvider; print('OK')"

# Provider resolution works for all three
python -c "
from pathlib import Path
from piframe.config_store import ConfigStore
from piframe.modules.sync import SyncModule
from piframe.providers import LocalProvider, OneDriveProvider, GooglePhotosProvider
import os

# Default (local)
cfg = ConfigStore(Path('/nonexistent'))
svc = SyncModule().create(cfg)
assert isinstance(svc._provider, LocalProvider)
svc.stop()

# OneDrive
try:
    os.environ['PIFRAME__SYNC__PROVIDER'] = 'onedrive'
    cfg2 = ConfigStore(Path('/nonexistent'))
    svc2 = SyncModule().create(cfg2)
    assert isinstance(svc2._provider, OneDriveProvider)
    svc2.stop()
finally:
    os.environ.pop('PIFRAME__SYNC__PROVIDER', None)

# Google
try:
    os.environ['PIFRAME__SYNC__PROVIDER'] = 'google'
    cfg3 = ConfigStore(Path('/nonexistent'))
    svc3 = SyncModule().create(cfg3)
    assert isinstance(svc3._provider, GooglePhotosProvider)
    svc3.stop()
finally:
    os.environ.pop('PIFRAME__SYNC__PROVIDER', None)

print('OK')
"
```

## Commit

```bash
bash eng/format.sh
bash eng/check.sh
git add -A
git commit -m "T13: regression — all tests pass, check.sh clean"
```