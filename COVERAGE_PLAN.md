# Differential Coverage Plan: 78% → >90%

## Current State

| Metric | Value |
|--------|-------|
| Changed lines (all) | 114 |
| Missing lines (all) | 25 |
| **Differential coverage** | **78%** |

### Missing lines by file (all)

| File | Missing Lines | Count |
|------|--------------|-------|
| `tests/test_integration.py` | 115, 218, 297, 350, 469, 475, 493, 499, 529, 535 | 10 |
| `src/piframe/settings_panel.py` | 354, 415, 456, 478, 571, 611, 615, 616, 701, 840 | 10 |
| `src/piframe/app.py` | 351 (`os.execve` in `restart()`) | 1 |
| `src/piframe/assets.py` | 65 (`Assets.load()`) | 1 |
| `src/piframe/widgets/time_picker.py` | 98 (popup rect drawing) | 1 |
| `src/piframe/widgets/wifi_list_item.py` | 86 (connected dot drawing) | 1 |
| `tests/conftest.py` | 174 (integration fixture `_on_device`) | 1 |

---

## Step 1: Exclude test files from diff-cover

Test files are already excluded from pytest (`--ignore=tests/test_integration.py`) but diff-cover still penalizes us for their uncovered lines. Since test code doesn't need test coverage, exclude them.

**Change in `eng/test.sh`:**

```diff
-    diff-cover "$COVERAGE_FILE" --fail-under=90
+    diff-cover "$COVERAGE_FILE" --fail-under=90 --exclude "test_*.py" "conftest.py"
```

**After exclusion:**

| Metric | Value |
|--------|-------|
| Changed lines (source only) | 49 |
| Missing lines (source only) | 14 |
| **Differential coverage** | **71%** |

To reach 90%: need ≤ 4 missing → must cover **10 of 14 lines**.

---

## Step 2: Add tests for 10 source-code lines

### 2a: `tests/test_app_state.py` — add 1 test

| Target | Line | Approach |
|--------|------|----------|
| `App.restart()` | 351 (`os.execve`) | Mock `os.execve` via `monkeypatch`, call `app.restart()`, assert `execve` was invoked with `sys.executable` |

```python
def test_restart_calls_execve(monkeypatch, tmp_path):
    """restart() calls os.execve to re-execute the process."""
    captured = []
    monkeypatch.setattr(os, "execve", lambda *a, **k: captured.append((a, k)))
    app = App(assets=_StubAssets(), config=ConfigStore(tmp_path / "config.toml"))
    app.restart()
    assert len(captured) == 1
    assert captured[0][0][0] == sys.executable
```

### 2b: `tests/test_assets.py` — new file, 1 test

| Target | Line | Approach |
|--------|------|----------|
| `Assets.load()` | 65 (font creation) | Mock `pygame.freetype.Font` to capture calls, call `Assets.load()`, assert 18 font loads (6 sizes × 3 font files) |

```python
def test_assets_load_creates_font_instances(monkeypatch):
    """Assets.load() creates pygame.freetype.Font for each size/font."""
    fonts_created = []
    mock = lambda path, size: (fonts_created.append((path, size)), pygame.Surface((1, 1)))[1]
    monkeypatch.setattr(pygame.freetype, "Font", mock)
    assets = Assets.load()
    assert len(fonts_created) == 18  # 6 sizes × 3 font files
    assert assets._regular is not None
```

### 2c: `tests/test_widgets.py` — add 2 tests

| Target | Line | Approach |
|--------|------|----------|
| `TimePicker.draw()` popup | 98 | Create TimePicker, set `_popup_open = True`, call `draw(screen)` |
| `WifiListItem.draw()` connected | 86 | Create WifiListItem with `is_connected=True`, call `draw(screen)` |

```python
def test_time_picker_draws_popup_when_open():
    """TimePicker draws the popup overlay when _popup_open is True."""
    picker = TimePicker(...)
    picker._popup_open = True
    screen = pygame.Surface((1024, 800))
    picker.draw(screen)  # hits line 98 (popup rect drawing)

def test_wifi_list_item_draws_connected_indicator():
    """WifiListItem draws a green dot when is_connected=True."""
    item = WifiListItem(WifiNetwork("Net", "WPA2", 80), is_connected=True, ...)
    screen = pygame.Surface((1024, 800))
    item.draw(screen)  # hits line 86 (pygame.draw.circle)
```

### 2d: `tests/test_settings_panel_sections.py` — new file, 6 tests

| Target | Lines | Section | Approach |
|--------|-------|---------|----------|
| Content background | 354 | `draw()` | Open panel in DISPLAY section, call `draw()` — content bg rect drawn |
| Brightness % label | 415 | Display | Same as above — brightness % text rendered next to slider |
| "Forget current" button | 456 | WiFi | Set `_wifi_status.connected = True`, navigate to WiFi, `draw()` |
| "Connect" button + password prompt | 478 | WiFi | Set `_wifi_password_ssid = "Test"`, navigate to WiFi, `draw()` |
| Git version in About | 571 | About | Mock `subprocess.check_output` → `"v1.2.3"`, navigate to ABOUT, `draw()` |
| Disk usage in About | 611, 615-616 | About | Mock `shutil.disk_usage` → fake usage stats, navigate to ABOUT, `draw()` |

```python
def test_draw_content_background(tmp_path):
    """draw() fills the content area background."""
    panel = _make_panel(tmp_path)
    panel._active_section = Section.DISPLAY
    panel.open()
    panel.draw(pygame.Surface((SCREEN_W, SCREEN_H)))  # hits 354

def test_display_brightness_percentage_label(tmp_path):
    """Display section renders brightness percentage label."""
    panel = _make_panel(tmp_path)
    panel._active_section = Section.DISPLAY
    panel.open()
    panel.draw(pygame.Surface((SCREEN_W, SCREEN_H)))  # hits 415

def test_wifi_forget_button_when_connected(tmp_path):
    """WiFi section shows 'Forget current' button when connected."""
    panel = _make_panel(tmp_path)
    panel._wifi_status = SimpleNamespace(connected=True, ssid="Home")
    panel._active_section = Section.WIFI
    panel.open()
    panel.draw(pygame.Surface((SCREEN_W, SCREEN_H)))  # hits 456

def test_wifi_connect_button_with_password_prompt(tmp_path):
    """WiFi section shows 'Connect' button when password prompt is active."""
    panel = _make_panel(tmp_path)
    panel._wifi_password_ssid = "SecureNet"
    panel._active_section = Section.WIFI
    panel.open()
    panel.draw(pygame.Surface((SCREEN_W, SCREEN_H)))  # hits 478

def test_about_git_version(tmp_path, monkeypatch):
    """About section shows git version from subprocess."""
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: b"v1.2.3")
    panel = _make_panel(tmp_path)
    panel._active_section = Section.ABOUT
    panel.open()
    panel.draw(pygame.Surface((SCREEN_W, SCREEN_H)))  # hits 571

def test_about_disk_usage(tmp_path, monkeypatch):
    """About section shows disk usage stats."""
    monkeypatch.setattr(shutil, "disk_usage", lambda p: SimpleNamespace(total=32*1024**3, used=5*1024**3, free=27*1024**3))
    panel = _make_panel(tmp_path)
    panel._active_section = Section.ABOUT
    panel.open()
    panel.draw(pygame.Surface((SCREEN_W, SCREEN_H)))  # hits 611, 615-616
```

---

## Summary

| Action | Lines Covered | Tests Added |
|--------|--------------|-------------|
| `eng/test.sh` — add `--exclude` | — (enables source-only scope) | — |
| `tests/test_app_state.py` — `restart()` | 1 | 1 |
| `tests/test_assets.py` — `Assets.load()` | 1 | 1 |
| `tests/test_widgets.py` — TimePicker + WifiListItem | 2 | 2 |
| `tests/test_settings_panel_sections.py` — 6 section draw paths | 6 | 6 |
| **Totals** | **10 of 14** | **10** |

### Projected result

| Metric | Value |
|--------|-------|
| Changed lines (source only) | 49 |
| Missing lines (after tests) | 4 |
| **Differential coverage** | **92%** |

The 4 remaining uncovered lines (`settings_panel.py: 701, 840` — update check button click + async worker) are in the Updates section's background thread logic and can be deferred to a follow-up.