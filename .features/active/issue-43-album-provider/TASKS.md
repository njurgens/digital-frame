# Tasks: Album Provider Abstraction

Ordered task list for the Album Provider Abstraction feature. Each task is self-contained with validation steps. A coding agent should complete tasks in order, run validation, commit, then proceed to the next.

**TDD approach:** Every task that adds or modifies code includes a "Write tests" step first. Tests go in `tests/test_providers.py` (new file) or `tests/test_config_store.py` / `tests/test_modules.py` (existing files). Run tests before implementing — they should fail. Implement the code — tests should pass.

## Phase 1: Foundation

- [ ] [T01: Create `providers/` package with `AlbumProvider` Protocol and `ProviderName` enum](TASK_01.md)
- [ ] [T02: Fix `album_provider.py` — rename to `DirectoryReader`, drop broken import](TASK_02.md)
- [ ] [T03: Add `provider` property and `_read_nested()` to `ConfigStore`](TASK_03.md)

## Phase 2: Provider Implementations

- [ ] [T04: Implement `OneDriveProvider` and `OneDriveConfig`](TASK_04.md)
- [ ] [T05: Implement `LocalProvider` and `LocalConfig`](TASK_05.md)
- [ ] [T06: Implement `GooglePhotosProvider` stub and `GooglePhotosConfig`](TASK_06.md)

## Phase 3: Wiring

- [ ] [T07: Refactor `SyncService` to accept `AlbumProvider`](TASK_07.md)
- [ ] [T08: Refactor `SyncModule.create()` to resolve provider by name](TASK_08.md)
- [ ] [T09: Update `SettingsPanel` / `SettingsModule` for new `SyncService` constructor](TASK_09.md)
- [ ] [T10: Add `_apply_env_overrides()` to `ConfigStore`](TASK_10.md)
- [ ] [T11: Update `_write_toml()` to handle nested dicts](TASK_11.md)
- [ ] [T12: Remove `framesync/` directory and update `eng/install.sh`](TASK_12.md)

## Phase 4: Config & Docs

- [ ] [T13: Create `config.devcontainer.toml`](TASK_13.md)
- [ ] [T14: Update `config.toml.example` with new structure](TASK_14.md)
- [ ] [T15: Update `.env.example` with env var override placeholders](TASK_15.md)

## Phase 5: Regression

- [ ] [T16: Ensure all existing tests pass and `eng/check.sh` is clean](TASK_16.md)