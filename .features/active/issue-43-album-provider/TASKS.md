# Tasks: Album Provider Abstraction

Ordered task list for the Album Provider Abstraction feature. Each task is self-contained with validation steps. A coding agent should complete tasks in order, run validation, commit, then proceed to the next.

**TDD approach:** Every task that adds or modifies code includes a "Write tests" step first. Tests go in `tests/test_providers.py` (new file) or `tests/test_config_store.py` / `tests/test_modules.py` (existing files). Run tests before implementing — they should fail. Implement the code — tests should pass.

## Phase 1: Foundation

- [ ] [T01: Verify `providers/` package with `AlbumProvider` Protocol and `ProviderName` enum](TASK_01.md) *(already implemented)*
- [ ] [T02: Verify `album_provider.py` uses `DirectoryReader`](TASK_02.md) *(already implemented)*
- [ ] [T03: Add `provider` property and `_read_nested()` to `ConfigStore`](TASK_03.md)

## Phase 2: Provider Implementations

- [ ] [T04: Implement `OneDriveProvider` and `OneDriveConfig`](TASK_04.md)
- [ ] [T05: Implement `LocalProvider` and `LocalConfig`](TASK_05.md)
- [ ] [T06: Implement `GooglePhotosProvider` stub and `GooglePhotosConfig`](TASK_06.md)

## Phase 3: Wiring

- [ ] [T07: Refactor `SyncService` and `SyncModule` for `AlbumProvider`](TASK_07.md)
- [ ] [T08: Add `_apply_env_overrides()` to `ConfigStore`](TASK_08.md)
- [ ] [T09: Update `_write_toml()` to handle nested dicts](TASK_09.md)
- [ ] [T10: Remove `framesync/` directory and update `eng/install.sh`](TASK_10.md)

## Phase 4: Config & Docs

- [ ] [T11: Create `config.devcontainer.toml`](TASK_11.md)
- [ ] [T12: Update `config.toml.example` with new structure](TASK_12.md)

## Phase 5: Regression

- [ ] [T13: Ensure all existing tests pass and `eng/check.sh` is clean](TASK_13.md)