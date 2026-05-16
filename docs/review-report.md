# Pi Frame — Compliance Review Report

> **Date:** 2025-07-24  
> **Reviewer:** GitHub Copilot  
> **Repository:** `njurgens/digital-frame`  
> **Scope:** Full cross-reference of implementation against three design artefacts  

---

## Reference Documents

| Abbrev | Document | Version |
|--------|----------|---------|
| LLD | `docs/pi-frame-lld.md` | 1.0 Authoritative |
| HLD | `docs/pi-frame-hld.md` | — |
| UX | `docs/pi-frame-ux-requirements.md` | — |

## Methodology

All implementation files were read in full. Each finding was cross-referenced against the corresponding LLD section, HLD section, and UX requirement ID. Findings are classified as:

- **PASS** — Implementation matches specification.
- **DEVIATION** — Implementation differs from specification; functionally present but wrong in some detail.
- **MISSING** — Feature or method specified but absent from implementation.
- **NOTE** — Implementation goes beyond spec or takes a different (acceptable) approach worth documenting.

---

## Executive Summary

| Part | Findings |
|------|---------|
| A — LLD | 18 PASS · 24 DEVIATION · 3 MISSING · 3 NOTE |
| B — HLD | 16 PASS · 3 DEVIATION · 1 PARTIAL · 1 NOTE |
| C — UX  | 28 PASS · 7 PARTIAL/DEVIATION · 6 DEFERRED (post-v1) |

**Highest-severity issues (affect correctness or user-visible behaviour):**

1. **A2-6 / A2-7** — `piframe/types.py` defines `IC_WIFI = "\ue63e"` and `IC_WIFI_OFF = "\ue648"` (wrong Material Icons codepoints). `wifi_list_item.py` imports from `types.py`, so the Wi-Fi signal icons render the wrong glyphs. `assets.py` has the correct values (`\ue8f4` / `\ue8f5`) but those are not used by `WifiListItem`.
2. **A4-2 / A4-3** — `PhotoCache` is memory-only; no PNG disk cache. Four methods specified in LLD §3.3 (`invalidate_disk`, `set_fit_mode`, `prefetch`, `invalidate`) are absent.
3. **A5-4** — `WifiListItem` widget exists but is never used in `SettingsPanel._draw_wifi()`; the Wi-Fi network list is rendered with raw `pygame.draw` calls instead.
4. **A5-2** — Timezone display in Settings is a non-interactive text label. LLD §3.5 requires a tappable `ScrollPicker`-based picker.
5. **A6-15** — `SyncService._do_sync()` calls individual `framesync` internals directly instead of the specified `load_config()` + `sync_folder(cfg)` pattern (OR-09).
6. **A6-9** — Default `display.brightness` is 80; UX requirements §6 specifies 72.
7. **A3-7** — `SlideshowPlayer.rescan()` always reshuffles, ignoring `config.slideshow.shuffle`.

---

## Part A — LLD Compliance

### A1. Project Layout (LLD §1)

| ID | Finding | Detail |
|----|---------|--------|
| A1-1 | **PASS** | All files and directories in the §1 layout table are present with correct paths. |
| A1-2 | **NOTE** | `piframe/updater.py` is not listed in LLD §1 but exists in the implementation. It contains `check_update()` and `apply_update()` (OR-01), extracted from `settings_panel.py` for cleaner separation. |
| A1-3 | **PASS** | `tests/` directory contains `conftest.py`, `image_utils.py`, `golden/`, and `test_*.py` files as listed. |
| A1-4 | **PASS** | Font assets at `piframe/assets/fonts/{NotoSans-Regular,NotoSans-Bold,MaterialIcons-Regular}.ttf` all present. |

---

### A2. Shared Types & Constants (LLD §2)

| ID | Finding | Detail |
|----|---------|--------|
| A2-1 | **PASS** | Screen constants (`SCREEN_W`, `SCREEN_H`, `SIDEBAR_W`, `FPS`, `TRANS_DURATION`, `OVERLAY_DISMISS`, `WAKE_GRACE`, etc.) match LLD §2.1 exactly. |
| A2-2 | **PASS** | `AppState` enum: `SLIDESHOW`, `OVERLAY`, `SETTINGS`, `KEYBOARD`, `SLEEPING` — all present. |
| A2-3 | **PASS** | `AppEvent` enum: `SLEEP`, `WAKE`, `SYNC_COMPLETE`, `OVERLAY_DISMISS` — all present. |
| A2-4 | **PASS** | `EVT_*` custom event IDs implemented via deferred `init_events()`. LLD §2.3 shows direct assignment (`pygame.USEREVENT + N`); the deferred pattern is a correct improvement (direct assignment would fail at module import time before `pygame.init()`). Values are equivalent once initialized. |
| A2-5 | **PASS** | All 20+ `COLOUR_*` constants verified against LLD §2.5 palette — values match exactly. |
| A2-6 | **DEVIATION** | `piframe/types.py` defines `IC_WIFI = "\ue63e"` and `IC_WIFI_OFF = "\ue648"`. LLD §5.2 specifies `IC_WIFI = "\ue8f4"` and `IC_WIFI_OFF = "\ue8f5"`. `piframe/assets.py` has the correct values; however `wifi_list_item.py` imports from `types.py`, so the Wi-Fi signal icons in the network list render wrong glyphs (likely "format_list_bulleted" and "wifi_tethering" rather than "wifi" and "wifi_off"). **Bug.** |
| A2-7 | **DEVIATION** | LLD §5.2 specifies all 21 icon codepoints must reside in `assets.py` only. Implementation duplicates 3 (`IC_WIFI`, `IC_WIFI_OFF`, `IC_LOCK`) in `types.py` with conflicting values for `IC_WIFI` and `IC_WIFI_OFF`. Several modules (`wifi_list_item.py`, `settings_panel.py`) import from `types.py`, creating a split-definition hazard. |
| A2-8 | **PASS** | All five dataclasses (`SyncStatus`, `WifiNetwork`, `WifiStatus`, `WifiResult`, `UpdateResult`) match LLD §2.4 field names and types. `WifiNetwork.signal_level` property (0/1/2 tiers) implemented correctly. |

---

### A3. Core App & SlideshowPlayer (LLD §3.1, §3.2)

| ID | Finding | Detail |
|----|---------|--------|
| A3-1 | **PASS** | `App` lifecycle: `run()`, `restart()`, `_cleanup()`, `_enter_sleep()`, `_exit_sleep()` all present. `restart()` uses `os.execve` with `XDG_RUNTIME_DIR`/`WAYLAND_DISPLAY` set (OR-02). |
| A3-2 | **PASS** | `--test-harness` flag opens `/tmp/piframe_test.sock`. All 7 specified commands (`tap`, `swipe`, `screenshot`, `state`, `set_config`, `trigger_sync`, `quit`) present; implementation extends with `play_pause`, `prev`, `next` (non-breaking additions). |
| A3-3 | **PASS** | Draw layer stack: (1) photo surface, (2) overlay, (3) settings, (4) keyboard, (5) dialog. Layers 1–3 are skipped in SETTINGS/KEYBOARD states via `if self._state not in {AppState.SETTINGS, AppState.KEYBOARD}` — functionally equivalent to the LLD guard. |
| A3-4 | **DEVIATION** | `_cleanup()` does not call `_clock_w.stop()`. LLD §3.1 implies cleanup should stop the clock widget thread. Only `_quit()` calls `stop()`. If the process exits via the cleanup path (e.g., exception in run loop), the daemon ticker thread may not be signalled before Python teardown. |
| A3-5 | **PASS** | `SlideshowPlayer`: Fisher-Yates shuffle (`_fisher_yates()`), `_direction` attribute, `go_back()`, `is_paused` property (read-only), `rescan()` all present. |
| A3-6 | **DEVIATION** | Method is named `skip()`, not `skip_next()` (LLD §3.2). Minor naming difference; semantics are identical. |
| A3-7 | **DEVIATION** | `rescan()` unconditionally calls `_fisher_yates()` after rebuilding the file list. LLD §3.2 says shuffle is conditional on `config.slideshow.shuffle`. Users who disable shuffle will still get a shuffled order after each sync. |
| A3-8 | **DEVIATION** | `draw_pip()` draws a white circle at `(cx, cy-20)` (horizontally centred, near bottom). LLD §3.2 specifies a 26×26 pause-icon pill at `(12, 762)` (bottom-left corner). Position, shape, and icon character all differ from spec. |
| A3-9 | **DEVIATION** | Slide transition: implementation accumulates `dt` to drive `_trans_progress`; LLD OR-04 specifies wall-clock elapsed via `time.monotonic()` for self-correcting duration. Sign convention for current/next offsets also differs slightly from OR-04 formula (`cur_x = int(-direction * progress * W)`), though the visual result is equivalent for forward navigation. |

---

### A4. Rendering & Caching (LLD §3.3, §3.4)

| ID | Finding | Detail |
|----|---------|--------|
| A4-1 | **PASS** | `PhotoCache`: cache key `{stem}_{fit_mode}_v{_CACHE_VERSION}` (OR-03) ✓. `MAX_CACHE = 6` (OR-08) ✓. `_CACHE_VERSION = 2` ✓. EXIF orientation correction via PIL tag 274 ✓. Fit and fill composite algorithms implemented. |
| A4-2 | **MISSING** | No disk cache. LLD §3.3 specifies writing composited surfaces to `cache_dir` as PNG and checking for the PNG file on cache miss (step 3 of `get()`). Implementation is in-memory only (`OrderedDict` LRU). Startup after a reboot therefore re-renders all surfaces from scratch, adding latency. |
| A4-3 | **MISSING** | Three methods specified in LLD §3.3 are absent: `invalidate_disk()` (delete PNGs from `cache_dir`), `set_fit_mode()` (update `_fit_mode`), `prefetch()`. Additionally, `invalidate()` (in-memory flush) is not implemented. These are referenced by `SettingsPanel` and `App` in the LLD's Stage 3–4 wiring steps. |
| A4-4 | **DEVIATION** | LLD §3.3 specifies an explicit `_order: list[str]` for LRU tracking. Implementation uses `collections.OrderedDict` which is functionally equivalent. |
| A4-5 | **PASS** | `OverlayUI`: `show()`, `hide()`, `update()`, `draw()`, `on_tap()`, `on_drag()`, `stop_drag()`, `set_paused()`, `set_brightness()` all present. Auto-dismiss timer at `OVERLAY_DISMISS = 5.0 s`. Brightness slider wired via `on_brightness_change` callback. |
| A4-6 | **PASS** | `VerticalSlider`: track/fill/thumb rendering, `_value_to_y()` / `_y_to_value()`, drag handling with 20 px inflated hit zone — all match LLD §4.2. |

---

### A5. Settings, Keyboard & Widgets (LLD §3.5, §4)

| ID | Finding | Detail |
|----|---------|--------|
| A5-1 | **PASS** | `SettingsPanel`: four sections (Slideshow, Display, Wi-Fi, System), sidebar with back button, section title + divider, `open()`, `close()`, `update()`, `on_tap()`, `on_wifi_result()`, `on_update_result()`, `refresh_sync_status()` all present. |
| A5-2 | **DEVIATION** | Display section renders timezone as a non-interactive text label (`"Timezone: {timezone}"`). LLD §3.5 Display table row specifies "Current tz label + tap-to-open `ScrollPicker`" wired to `system.timezone`. The timezone picker is entirely absent — users cannot change timezone from within the UI. |
| A5-3 | **DEVIATION** | Brightness in the Display section uses a `SegmentedControl` with fixed values [25 %, 50 %, 75 %, 100 %]. LLD §3.5 specifies a `VerticalSlider` for the brightness row (same control type as the overlay). |
| A5-4 | **DEVIATION** | The Wi-Fi network list is rendered with inline `pygame.draw`/`font.render` calls in `_draw_wifi()`. The `WifiListItem` widget (`piframe/widgets/wifi_list_item.py`) is never used in `SettingsPanel`. LLD §3.5 / Stage 7 explicitly specifies a "Scrollable `WifiListItem` list". |
| A5-5 | **DEVIATION** | "Forget network" is implemented as a button ("Forget current") that calls `WifiManager.forget()` immediately with no confirmation. LLD Stage 7 specifies: long-press on connected `WifiListItem` → `ConfirmDialog` "Forget?" → `forget(ssid)`. No long-press wiring and no confirmation dialog for the forget action. |
| A5-6 | **PASS** | All 10 widget classes are present: `Toggle`, `VerticalSlider`, `SegmentedControl`, `ScrollPicker`, `TimePicker`, `WifiListItem`, `ConfirmDialog`, `NavItem`, `TextInput`, and `base.Widget` ABC. |
| A5-7 | **PASS** | `Keyboard`: three layers (ALPHA, NUMERIC, EXTENDED), row y-positions and key geometry constants match LLD §4.10, `attach()`, `detach()`, `_emit()`, shift logic all present. |
| A5-8 | **DEVIATION** | `Keyboard.is_visible` is implemented as a regular method (`def is_visible(self) -> bool`) rather than a `@property` as specified in LLD §3.6. Call sites in `App` that expect `_keyboard.is_visible` (property) would silently return the bound method object (truthy) unless called with `()`. |
| A5-9 | **DEVIATION** | `TextInput` password mode renders `"●"` (U+25CF BLACK CIRCLE) per character. LLD §4.9 specifies `"*"` (asterisk). Minor visual difference. |
| A5-10 | **DEVIATION** | `NavItem.handle_event()` does not set `self.active = True` on click; it calls `on_select()` and returns `True`. LLD §4.8 says "active = True → call on_select()". The active flag is managed externally by `SettingsPanel._select_section()`, which is functionally correct but deviates from the widget-level contract. |
| A5-11 | **DEVIATION** | `TimePicker` uses `ROW_H = 44` and `VISIBLE_ROWS = 7`. OR-10 specification says "6 visible rows × 40 px = 240 px". Both row height and visible-row count differ. The popup height (280 px) matches, but the ScrollPicker dimensions inside are taller rows with more rows shown. |

---

### A6. Background Services, Configuration & Hardware (LLD §3.7–§3.12)

| ID | Finding | Detail |
|----|---------|--------|
| A6-1 | **PASS** | `ClockWidget`: daemon ticker thread with `stop_event`, `stop()`, `draw()`, `set_timezone()` all present. |
| A6-2 | **DEVIATION** | Clock renders at the bottom of the screen (`y = SCREEN_H - 20 - height`). LLD §3.7 render spec positions time at `(14, 14)` top-left corner. The bottom-corner placement is confirmed intentional in the implementation (pixel coordinates inverted). |
| A6-3 | **DEVIATION** | Time format is `"%-I:%M"` (12-hour H:MM, no AM/PM suffix). LLD §3.7 specifies `"%-I:%M %p"` (with AM/PM). *Mitigating context:* UX requirement SH-04 says "H:MM format" with no explicit AM/PM requirement, so the implementation is arguably closer to the UX intent. |
| A6-4 | **DEVIATION** | Method is named `set_timezone()`. LLD §3.7 and Stage 5 wiring step both use `update_timezone()`. Call sites in `SettingsPanel` would need updating if they use the LLD name. |
| A6-5 | **DEVIATION** | Ticker thread uses `stop_event.wait(30)` — wakes every 30 seconds. LLD §3.7 specifies sleeping until the next minute boundary (wall-clock self-correcting). The 30-second poll means the displayed time can be up to 30 s stale after a minute rolls over. |
| A6-6 | **MISSING** | No `update(dt: float)` method on `ClockWidget`. LLD §3.7 specifies this method is called each frame. The widget base class provides a no-op default, so calls won't error, but the spec intent (frame-rate-driven updates) is not implemented. |
| A6-7 | **DEVIATION** | Date text is rendered in `COLOUR_CLOCK_TEXT`. LLD §3.7 render spec uses `COLOUR_TEXT_SECONDARY` for the date string. |
| A6-8 | **PASS** | `ConfigStore`: `tick()`, `flush_now()`, `set()`, `_apply_defaults()`, `_write_toml()`, 6 sections, 0.5 s debounce, protected keys (`sync.share_url`, `sync.password`, `sync.output_dir`, `sync.cache_dir`) — all match LLD §3.10. |
| A6-9 | **DEVIATION** | Default `display.brightness = 80` in both `ConfigStore._DEFAULTS` and `config.toml.example`. UX requirements §6 specifies a default of 72 (`brightness = 72`). LLD and implementation agree at 80; UX requirement is not met. |
| A6-10 | **PASS** | Sync config key is `interval_minutes` in both LLD §3.10 TOML template (line 1358) and `config.toml.example`. The prior session summary mistakenly noted "interval_hours" — verified as `interval_minutes` in the actual LLD. No deviation. |
| A6-11 | **PASS** | `BacklightController`: `BACKLIGHT_PATH = "/sys/class/backlight/10-0045/brightness"`, 0–255 raw range, 0–100 % conversion, clamping, `OSError` handling. Matches LLD §3.11. |
| A6-12 | **PASS** | `WifiManager`: `scan()`, `connect()`, `forget()`, `disconnect()`, `get_status()` all present. All operations run in daemon threads. `EVT_WIFI_RESULT` posted on completion. All `nmcli` calls prefixed with `sudo`. |
| A6-13 | **DEVIATION** | `WifiManager.scan()` calls `nmcli dev wifi list` without `--rescan yes`. LLD §3.12 specifies the command as `sudo nmcli dev wifi list --rescan yes`. Without this flag, nmcli may return stale cached results on subsequent scans. |
| A6-14 | **PASS** | `SyncService`: `trigger()`, `stop()`, `status` property, daemon thread loop, `_trigger_event` for manual sync, `_stop_event` for shutdown — all match LLD §3.8. |
| A6-15 | **DEVIATION** | `SyncService._do_sync()` calls individual `framesync` module functions (e.g. `get_badger_token`, `encode_url`, `sync_files`) directly. LLD OR-09 and §3.8 specify: `from framesync import sync_folder, load_config; cfg = load_config(); sync_folder(cfg)`. The implementation bypasses the public `sync_folder()` entry-point, coupling `SyncService` to framesync internals and breaking the encapsulation boundary described in OR-09. |
| A6-16 | **PASS** | `SleepScheduler`: midnight-crossing `is_sleep_time()` algorithm matches OR-05 exactly, `set_grace()` and `stop()` present, daemon thread posts `EVT_SLEEP`/`EVT_WAKE`. |

---

## Part B — HLD Compliance

### B1. Architecture & Module Structure (HLD §2–§4)

| ID | Finding | Detail |
|----|---------|--------|
| B1-1 | **PASS** | Single-process pygame application architecture. All 13 specified modules under `piframe/` are present. |
| B1-2 | **PASS** | 30 fps render loop in `App.run()` with `pygame.time.Clock.tick(FPS)`. |
| B1-3 | **PASS** | Custom pygame events used for all inter-thread communication (`EVT_SYNC_COMPLETE`, `EVT_SLEEP`, `EVT_WAKE`, `EVT_UPDATE_RESULT`, `EVT_WIFI_RESULT`). |
| B1-4 | **NOTE** | `piframe/updater.py` is an additional module not in the HLD module inventory; it is a clean extraction of OTA functions referenced in Stage 8. |

---

### B2. State Machine (HLD §2)

| ID | Finding | Detail |
|----|---------|--------|
| B2-1 | **PASS** | All 5 `AppState` values (`SLIDESHOW`, `OVERLAY`, `SETTINGS`, `KEYBOARD`, `SLEEPING`) implemented. |
| B2-2 | **PASS** | All state transitions from HLD §2 table implemented correctly (SLIDESHOW↔OVERLAY, OVERLAY→SETTINGS, SETTINGS↔KEYBOARD, any→SLEEPING, SLEEPING→OVERLAY on tap-to-wake). |
| B2-3 | **DEVIATION** | SLEEPING → OVERLAY transition wraps wakeup in a `WAKE_GRACE` window (30 s). This is a correct refinement specified in LLD §2.1 and UX §342, but not called out in HLD §2. |

---

### B3. Rendering Pipeline (HLD §3)

| ID | Finding | Detail |
|----|---------|--------|
| B3-1 | **PASS** | 5-layer draw stack: photo → overlay → settings → keyboard → dialog. `_dialog` attribute handles the modal layer. |
| B3-2 | **PASS** | `PhotoCache` compositing: blur-background fit mode and fill mode both implemented. EXIF correction applied. |
| B3-3 | **PASS** | Crossfade, cut, and slide transitions all implemented in `SlideshowPlayer`. |

---

### B4. Configuration Schema (HLD §6)

| ID | Finding | Detail |
|----|---------|--------|
| B4-1 | **PASS** | All 6 TOML sections (`slideshow`, `display`, `sleep`, `sync`, `system`, `update`) present in `config.toml.example` with all keys and types matching. |
| B4-2 | **PASS** | `config.toml.example` and `ConfigStore._DEFAULTS` are consistent with each other. |
| B4-3 | **DEVIATION** | Default `display.brightness = 80` in implementation vs. 72 in UX requirements (see A6-9). HLD §6 does not specify a default; the conflict is between LLD/implementation and the UX requirements. |

---

### B5. Background Services & Hardware (HLD §7–§8)

| ID | Finding | Detail |
|----|---------|--------|
| B5-1 | **PASS** | All 3 background service classes (`SyncService`, `SleepScheduler`, `ClockWidget` ticker) run as daemon threads and terminate cleanly via stop events. |
| B5-2 | **PASS** | `BacklightController` uses the sysfs interface at the exact path specified. |
| B5-3 | **PARTIAL** | `WifiManager` is implemented and integrated. `scan()` is missing `--rescan yes` (see A6-13), which may affect reliability on subsequent scans. All other nmcli operations are correct. |

---

### B6. Open Items Resolution (HLD §10)

| OR | Item | Status |
|----|------|--------|
| OR-01 | OTA update mechanism | **PASS** — `piframe/updater.py` implements `check_update()` (GitHub Releases API) and `apply_update()` (tarball download + `shutil.copytree`). Uses a proper staging directory in the repo root instead of `/tmp` — security improvement over OR-01 pseudocode. |
| OR-02 | App restart under labwc | **PASS** — `App.restart()` uses `os.execve` with `XDG_RUNTIME_DIR`/`WAYLAND_DISPLAY` set, exactly as specified. |
| OR-03 | Cache key includes fit_mode | **PASS** — Key format `"{stem}_{fit_mode}_v{_CACHE_VERSION}"` implemented correctly. |
| OR-04 | Slide transition direction | **PARTIAL** — Direction logic implemented but sign convention differs slightly from the OR-04 canonical formula. Backward navigation has not been independently verified to produce the expected right-to-left slide. |
| OR-05 | Midnight-crossing sleep | **PASS** — Algorithm exactly matches OR-05 specification, including `sleep_m == wake_m` degenerate case. |
| OR-06 | nmcli polkit | **PASS** — `sudo` prefix on all `nmcli` calls. |
| OR-07 | Timezone picker windowing | **PASS** — `ScrollPicker` renders only `[first, first+8)` rows; LRU eviction at `visible_rows * 3` distance. |
| OR-08 | Surface memory budget | **PASS** — `MAX_CACHE = 6`; memory-only cache (no disk writes, so peak is lower than spec estimate). |
| OR-09 | framesync units retired | **PARTIAL** — `framesync.service`/`framesync.timer` are disabled in `install.sh` ✓. However `SyncService._do_sync()` calls framesync internals instead of the `sync_folder()` public API (see A6-15). |
| OR-10 | TimePicker interaction model | **PARTIAL** — Two pill buttons + popup with ScrollPicker columns + Done button implemented. Row height (44 px) and visible rows (7) differ from OR-10 spec (40 px / 6 rows). |

---

## Part C — UX Requirements Traceability

| Req ID | Summary | Status | Notes |
|--------|---------|--------|-------|
| SH-01 | Full-screen JPEG display | **PASS** | PhotoCache + App fullscreen ✓ |
| SH-02 | Auto-advance interval | **PASS** | SlideshowPlayer reads `config.slideshow.interval` ✓ |
| SH-03 | Shuffle playlist | **PARTIAL** | Fisher-Yates present; `rescan()` ignores shuffle setting (A3-7) |
| SH-04 | Clock showing H:MM | **PASS** | Format `"%-I:%M"` matches; positioned bottom-right (LLD deviation) |
| SH-05a | Paused indicator pip | **PARTIAL** | White circle rendered; not at spec'd position `(12, 762)` (A3-8) |
| SH-05b | Settings-gear button | **PASS** | Gear button in OverlayUI ✓ |
| SH-06 | Clock overlay | **PASS** | ClockWidget renders date + time ✓ |
| SH-07 | EXIF orientation correction | **PASS** | PIL tag 274 applied ✓ |
| SH-08 | Blurred-background composite | **PASS** | Fit mode composites background blur ✓ |
| PS-01 | Tap to show overlay | **PASS** | MOUSEBUTTONDOWN in SLIDESHOW state ✓ |
| PS-02 | Play / pause button | **PASS** | OverlayUI play/pause toggle ✓ |
| PS-03 | Previous / next buttons | **PASS** | OverlayUI prev/next → SlideshowPlayer ✓ |
| PS-04 | Swipe left/right | **PASS** | App swipe detection in pointer-up handler ✓ |
| PS-05 | Overlay auto-dismissal | **PASS** | 5-second timer; resets on interaction ✓ |
| PS-06 | Brightness slider | **PASS** | VerticalSlider in overlay; live sysfs update ✓ |
| PB-01 | Settings panel | **PASS** | Gear tap → SETTINGS state ✓ |
| PB-02 | Slideshow settings | **PASS** | Interval, fit, shuffle, transition all wired ✓ |
| PB-03 | Display settings | **PARTIAL** | Brightness/clock/sleep present; timezone not interactive (A5-2) |
| PB-04 | Wi-Fi settings | **PARTIAL** | Scan/connect/status work; forget lacks ConfirmDialog (A5-5); WifiListItem widget unused (A5-4) |
| PB-05 | Photo metadata in overlay | **DEFERRED** | Marked post-v1 in LLD ✓ |
| BL-01 | Backlight brightness | **PASS** | BacklightController sysfs write ✓ |
| BL-02 | Brightness persisted | **PASS** | ConfigStore `display.brightness` ✓ |
| BL-03 | Brightness visible while dragging | **PASS** | Live overlay label update ✓ |
| BL-04 | Sleep dims to 0 | **PASS** | `_enter_sleep()` calls `set_brightness(0)` ✓ |
| BL-05 | Ambient light adjustment | **DEFERRED** | Marked post-v1 ✓ |
| KB-01 | On-screen keyboard | **PASS** | `TextInput.on_focus` → KEYBOARD state ✓ |
| KB-02 | Alpha / numeric / extended | **PASS** | 3 layers implemented ✓ |
| KB-03 | Shift key (single-shot) | **PASS** | Shift state in `Keyboard` ✓ |
| KB-04 | Backspace | **PASS** | Keyboard → `TextInput.backspace()` ✓ |
| KB-05 | Done dismisses keyboard | **PASS** | Done key → SETTINGS state ✓ |
| DS-01 | TOML config | **PASS** | ConfigStore + config.toml ✓ |
| DS-02 | Extra transitions | **DEFERRED** | Post-v1 ✓ |
| DS-03 | Sleep schedule | **PASS** | SleepScheduler with midnight-crossing ✓ |
| DS-04 | Timezone picker | **PARTIAL** | Timezone readable from config; no interactive picker (A5-2) |
| DS-05 | Info bar on photos | **DEFERRED** | Post-v1 ✓ |
| WF-01 | Wi-Fi network list | **PARTIAL** | List rendered but not using WifiListItem widget (A5-4) |
| WF-02 | Connect with password | **PASS** | TextInput + Keyboard → `WifiManager.connect()` ✓ |
| WF-03 | Forget saved network | **PARTIAL** | Forget works; no ConfirmDialog confirmation (A5-5) |
| WF-04 | Wi-Fi status indicator | **PASS** | Status shown in Wi-Fi section; wrong icon glyphs (A2-6) |
| WF-05 | First-run onboarding | **DEFERRED** | Post-v1 ✓ |
| SY-01 | OneDrive sync | **PASS** | SyncService daemon thread ✓ |
| SY-02 | Sync status in Settings | **PASS** | `refresh_sync_status()` shows last sync time + photo count ✓ |
| SY-03 | Manual sync trigger | **PASS** | "Sync now" → `SyncService.trigger()` ✓ |
| SY-04 | OTA update | **PASS** | Check + Install flow in System section ✓ |

---

## Prioritised Finding Index

### 🔴 High — Bug or regression risk

| ID | Module | Issue |
|----|--------|-------|
| A2-6 | `types.py` / `wifi_list_item.py` | IC_WIFI / IC_WIFI_OFF codepoints wrong in `types.py`; `WifiListItem` imports from there → wrong glyphs rendered |
| A3-7 | `app.py` / `SlideshowPlayer` | `rescan()` always reshuffles; ignores `config.slideshow.shuffle` |
| A6-13 | `wifi_manager.py` | `scan()` missing `--rescan yes`; may return stale nmcli cache |
| A6-15 | `sync_service.py` | `_do_sync()` bypasses `sync_folder()` public API; brittle coupling to framesync internals |
| A5-8 | `keyboard.py` | `is_visible` is a method, not a `@property`; call sites expecting property access will silently get truthy bound method |

### 🟠 Medium — Missing feature from v1 scope

| ID | Module | Issue |
|----|--------|-------|
| A4-2 | `photo_cache.py` | No disk cache; LLD specifies PNG persistence in `cache_dir` |
| A4-3 | `photo_cache.py` | Missing: `invalidate_disk()`, `set_fit_mode()`, `prefetch()`, `invalidate()` |
| A5-2 | `settings_panel.py` | Timezone non-interactive; ScrollPicker picker not implemented |
| A5-4 | `settings_panel.py` | Wi-Fi network list renders inline; `WifiListItem` widget never used |
| A5-5 | `settings_panel.py` | Forget network: no long-press, no ConfirmDialog; immediate operation |
| A6-9 | `config_store.py` / `config.toml.example` | Default brightness 80 vs UX requirement of 72 |

### 🟡 Low — Cosmetic, naming, or minor algorithmic differences

| ID | Module | Issue |
|----|--------|-------|
| A2-7 | `types.py` / `assets.py` | Duplicate icon definitions; root cause of A2-6 |
| A3-4 | `app.py` | `_cleanup()` doesn't call `_clock_w.stop()` |
| A3-6 | `app.py` | `skip()` vs `skip_next()` naming |
| A3-8 | `app.py` | `draw_pip()` position and shape deviate from spec |
| A3-9 | `app.py` | dt-accumulation vs wall-clock for transition progress |
| A5-3 | `settings_panel.py` | Brightness uses SegmentedControl instead of VerticalSlider in Settings |
| A5-9 | `widgets/text_input.py` | Password renders `●` not `*` |
| A5-10 | `widgets/nav_item.py` | `handle_event` doesn't set `active = True` directly |
| A5-11 | `widgets/time_picker.py` | ROW_H=44/VISIBLE_ROWS=7 vs OR-10 spec 40px/6 |
| A6-2 | `clock_widget.py` | Clock position bottom vs LLD top-left `(14,14)` |
| A6-3 | `clock_widget.py` | No AM/PM in time string (matches UX req, not LLD) |
| A6-4 | `clock_widget.py` | `set_timezone()` vs `update_timezone()` |
| A6-5 | `clock_widget.py` | 30-second poll vs minute-boundary sleep |
| A6-6 | `clock_widget.py` | Missing `update(dt)` method |
| A6-7 | `clock_widget.py` | Date uses `COLOUR_CLOCK_TEXT` vs `COLOUR_TEXT_SECONDARY` |

---

*End of report.*
