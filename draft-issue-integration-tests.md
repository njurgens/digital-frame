# Integration tests: drive the real app over its test harness (Playwright-style)

## Background

The old integration tests (`tests/test_integration.py`) have been removed. They
were platform-specific: they SSH'd into one particular Raspberry Pi, launched the
app through a legacy entry point, bridged the app's Unix socket over socat, and
compared golden screenshots. They could not run in the devcontainer or CI, and
they tested the deployment as much as the app.

The app already has the right seed for what we actually want: the
`--test-harness` flag (`src/piframe/app.py`) starts a JSON-over-Unix-socket
control channel (`/tmp/piframe_test.sock`) that can query app state, drive the
UI (tap/swipe), change config values, trigger a sync, take a screenshot, and
quit the app. Commands are executed on the app's main loop
(`_drain_harness_queue`): `tap` and `swipe` are injected as real pygame
input events, while the other commands read or invoke the app directly.

## Goal

Add integration tests that run the **real app** — the `slideshow` entry point,
the same binary labwc autostart runs — with `--test-harness`, and drive and
observe it through that control channel. The relationship should be the one
Playwright has to a browser: the test launches the app as a child process,
talks to it over a documented protocol, and asserts on what the app reports —
without depending on any particular machine, OS, or display.

## Requirements

- **Platform-independent.** Tests run anywhere the app runs: devcontainer, CI,
  and the Pi. No SSH, no hardcoded host, no device-specific paths, no golden
  screenshots. The display is the dummy driver (`SDL_VIDEODRIVER=dummy`), the
  same one the unit tests already use.
- **Hermetic.** Mock Wi-Fi and a local (or mock) album provider; no network,
  no OneDrive credentials, no real display, no real Wi-Fi.
- **Drives the real app.** Tests launch the installed `slideshow` console
  script (not a re-implementation of the app), as a child process, and
  communicate only through the harness channel.
- **Documented, stable protocol.** The harness command/response schema
  (`state`, `tap`, `swipe`, `play_pause`, `prev`, `next`, `set_config`,
  `trigger_sync`, `screenshot`, `quit`) is to be documented in the LLD and
  treated as a contract: tests may depend on it, and changing it is a design
  change, not an implementation detail.
- **Part of the test gate.** A script (e.g. `eng/test-integration.sh`, or a
  flag on `eng/test.sh`) runs them headlessly in the devcontainer; they pass
  on a clean checkout with no device attached.

## Out of scope

- Unit tests — the existing suite already covers component behaviour.
- Pixel-perfect visual comparison — the old golden-image approach is exactly
  what made the tests platform-specific.
- Testing the deployment itself (rsync, autostart, sudoers) — that stays a
  manual step.

## Definition of done

- [ ] Harness protocol documented in the LLD (commands, responses, error shape)
- [ ] Harness code unit-tested locally (no device required)
- [ ] A first set of integration tests (≥ 5) launches the app, drives it over
      the harness, and asserts on reported state — e.g. app state transitions,
      a config change taking effect, a sync completing, a tap navigating the UI
- [ ] Runs green in the devcontainer with a dummy display; no Pi required
- [ ] Wired into the test gate so a broken app is caught before deploy

## Notes

- The current harness lives in `src/piframe/app.py`: `_start_harness`,
  `_harness_loop`, `_handle_harness_cmd`, `_drain_harness_queue`,
  `_exec_harness_cmd`.
- The deleted tests' `AppHarness` client class is a useful reference for the
  client side of the protocol (connect, send a JSON line, read a JSON line).
- The harness socket path is currently hardcoded to `/tmp/piframe_test.sock`;
  making it configurable (or per-process) is a candidate improvement so tests
  can run in parallel.
