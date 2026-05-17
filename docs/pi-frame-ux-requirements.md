# Pi Frame — UX requirements spec

## Purpose

This document is the requirements input for producing a High-Level Design (HLD) and
Low-Level Design (LLD) for the Pi Frame application. The coding agent should use this
document to understand all UI/UX behaviour before designing the software architecture.

---

## Platform & constraints

| Property | Value |
|---|---|
| Hardware | Raspberry Pi 3A+ |
| Display | Waveshare 10.1" DSI LCD (C), 1280 × 800, IPS |
| Compositor | labwc (Wayland) |
| Primary HID | 10-point capacitive touch. No physical buttons. |
| Runtime | Python / pygame (existing PoC slideshow) |
| Config format | TOML |
| On-screen keyboard | Custom pygame widget (not wvkbd / Squeekboard) |

---

## Architecture notes for the designer

- The app is a single pygame process running fullscreen under labwc.
- All UI (slideshow, overlay, settings panel, on-screen keyboard) is rendered by
  pygame — there is no web stack or GTK.
- Backlight is controlled by writing an integer 0–255 to
  `/sys/class/backlight/*/brightness`. The agent should verify on the target device
  whether this path requires a sudoers rule or a small privileged helper daemon.
- Wi-Fi management backend (nmcli / wpa_supplicant / other) is to be determined by
  the agent via SSH inspection of the target Raspbian image. The requirement is the
  UX behaviour; the implementation mechanism is the agent's decision.
- All persistent settings are stored in a single TOML config file. The file must be
  human-readable and editable over SSH without running the app.

---

## 1. Slideshow (idle state)

### SH-01 — Fullscreen display
The default application state is a fullscreen photo slideshow. No UI chrome is visible
during normal playback.

### SH-02 — Tap to show overlay
A single short tap anywhere on the screen surfaces the transient control overlay
(see Section 3). Tap recognition is low-movement only; drag gestures do not trigger
the overlay.

### SH-03 — Swipe navigation
A horizontal swipe gesture (left or right) during slideshow advances to the next or
previous photo respectively, independent of whether the overlay is showing.

### SH-04 — Clock overlay
A clock and date are displayed directly on the photo at all times, without requiring
the overlay to be active. Default position: top-left corner.

- Time format: `H:MM` (24-hour, no leading zero)
- Date format: `Weekday, Month D` (e.g. `Friday, May 15`)
- Rendered with a subtle text shadow or semi-transparent backing to remain legible
  against any photo.
- Visibility is user-configurable (see DS-01). Default: on.

### SH-05 — Paused indicator
When playback is paused and the overlay has been dismissed, a small pause icon pip
persists in the bottom-left corner of the screen so the user can tell at a glance that
the frame is paused and not frozen.

---

## 2. Photo sources & sync

### PS-01 — OneDrive (primary source)
OneDrive sync via the existing Badger token mechanism continues as the primary photo
source. The sync runs as a background process on a configurable schedule.

### PS-02 — Local cache (offline fallback)
Photos are cached locally after sync. If the device has no network connection, the
cached folder is used as the source without user intervention.

### PS-03 — Sync status
The Slideshow settings section (see Section 5.1) shows:
- Timestamp of last successful sync
- Total number of photos in the local cache
- A manual "Sync now" button that triggers an immediate sync

---

## 3. Transient control overlay

The overlay appears on tap and auto-dismisses after 5 seconds of no interaction.
When playback is paused the auto-dismiss timer is suspended — the overlay stays
visible until the user explicitly taps elsewhere to dismiss it.

The overlay renders as a semi-transparent dark scrim over the current photo.
All overlay controls are rendered above the scrim. The clock (Section 1, SH-04)
sits above the scrim as well, so it remains readable when the overlay is active.

A thin progress bar spanning the full top edge of the screen drains from full to empty
over the 5-second dismiss window, giving visual feedback. It is hidden when the timer
is suspended (paused state).

### 3.1 — Layout

```
┌──────────────────────────────────────────┬──────┐
│  10:42                                   │      │
│  Friday, May 15          [clock always]  │  ⚙   │  ← settings gear
│                                          │      │
│                                          │  🔆  │  ← sun-bright icon
│                                          │      │
│                                          │ [  ] │  ← vertical brightness slider
│                                          │      │
│      ⏮        ⏸/▶        ⏭             │  🔅  │  ← sun-dim icon
│                                          │  72% │  ← brightness %
└──────────────────────────────────────────┴──────┘
 ←————————— playback controls ————————————  right
                                            col
```

**Right column (~52 px wide):** top to bottom — settings gear button, then brightness
column (bright sun icon, vertical slider, dim sun icon, numeric percentage readout).

**Bottom bar (full width minus right column):** playback controls centred horizontally —
Previous, Play/Pause (slightly larger), Next.

### 3.2 — Playback controls (PB-01 – PB-04)

| Control | Behaviour |
|---|---|
| Previous | Skip to previous photo immediately |
| Play / Pause | Toggle slideshow playback. Icon updates to reflect state. |
| Next | Skip to next photo immediately |

### 3.3 — Brightness slider (BL-01, BL-02)

A vertical range slider in the right column, oriented bright-end up. Dragging up
increases brightness, down decreases. The numeric readout below updates live.
Moving the slider writes immediately to `/sys/class/backlight/*/brightness` (mapped
0–100 % → 0–255). The value is also saved to the TOML config (BL-04).

### 3.4 — Settings button (SH-05)

Tapping the gear icon transitions to the full-screen settings panel (Section 5).
The overlay dismisses and the settings panel animates in.

---

## 4. On-screen keyboard

All text input in the application uses a custom pygame keyboard widget.
No system keyboard (wvkbd, Squeekboard, matchbox) is used.

### KB-01 — Trigger
The keyboard slides up from the bottom of the screen whenever a text input field
receives focus. It slides back down on dismiss.

### KB-02 — Layers
Three layers accessible via toggle keys:

| Layer | Key label |
|---|---|
| Alpha (default) | `ABC` |
| Numeric / symbols | `123` |
| Extended symbols | `#+=` |

### KB-03 — Key sizing
Keys must be large enough for reliable single-finger tap at 10.1". The LLD should
calculate minimum key dimensions from the available width and a minimum tap target
of 44 px. QWERTY layout.

### KB-04 — Dismiss
- A `Done` key in the bottom-right corner commits the input and dismisses.
- Tapping outside the keyboard area also dismisses.

### KB-05 — Password mode
When the focused field is a password field:
- Characters are replaced with `•` immediately after entry.
- A show/hide toggle (eye icon) in the input field reveals/obscures the plaintext.
- The keyboard itself is identical to normal alpha mode.

---

## 5. Settings panel

The settings panel is a full-screen dark-themed UI that replaces the slideshow view.
It is organised as a left sidebar with navigation items and a content area to the right.

### Navigation sidebar (~26 % of screen width)

Contains, top to bottom:
1. A back button (`← Back to frame`) that returns to the slideshow
2. Four navigation items: Slideshow, Display, Wi-Fi, System

The active section is visually highlighted. No nested navigation — all settings fit
within one level.

---

### 5.1 — Slideshow section

| Setting | Control | Default |
|---|---|---|
| Interval | Segmented control: `5 s` / `15 s` / `30 s` / `1 m` / `5 m` | `30 s` |
| Shuffle | Toggle | On |
| Fit mode | Segmented: `Fit` / `Fill` | `Fit` |
| Transition | Segmented: `Crossfade` / `Cut` / `Slide` | `Crossfade` |
| OneDrive sync status | Read-only: last synced time, photo count + "Sync now" button | — |

**Fit vs Fill:** Fit letterboxes the photo (black bars if aspect ratios differ). Fill
crops the photo to fill the screen with no bars.

---

### 5.2 — Display section

| Setting | Control | Default |
|---|---|---|
| Show clock | Toggle | On |
| Sleep schedule | Toggle (enable/disable the schedule) | Off |
| Sleep window | Two time pickers: sleep time → wake time (grayed out if schedule disabled) | 22:00 → 07:00 |
| Timezone | Segmented: `Auto` / `Manual` | `Auto` |
| Timezone region | Text field (shown only when Manual) | — |

**Sleep schedule behaviour:** When the current time falls within the sleep window,
backlight brightness is set to 0. On wake time, brightness is restored to the
configured value. A tap during sleep turns the display on temporarily (same overlay
mechanic) but does not permanently override the schedule.

---

### 5.3 — Wi-Fi section

**Connected network row (shown when connected):**
- SSID name
- IP address
- "Connected" badge
- "Forget" button (destructive style)

**Available networks list:**
- Scanned SSIDs with signal-strength icons (3 levels)
- Tapping an SSID that requires a password opens the on-screen keyboard with a
  password-mode text field
- Tapping an open network connects immediately
- A spinner / status indicator shows connecting / failed state

**Error states:**
- Connection failed: inline error message below the SSID row, auto-clears after 4 s
- No networks found: empty state with a "Scan again" button

---

### 5.4 — System section

**Device info (read-only):**
- App version
- IP address
- Uptime
- Storage used / total

**Actions:**

| Action | Style | Behaviour |
|---|---|---|
| Check for updates | Neutral | Pulls latest release from GitHub; shows version comparison; prompts to apply |
| Restart app | Neutral | Restarts the pygame process without rebooting the Pi |
| Shutdown | Destructive | Confirmation dialog → `sudo shutdown now` |
| Reboot | Destructive | Confirmation dialog → `sudo reboot` |

Destructive actions require a confirmation step (a modal dialog with Cancel / Confirm)
before executing.

---

## 6. TOML config schema (reference)

The config file stores all user-modifiable settings. Keys below are illustrative names;
the LLD should formalise the schema.

```toml
[slideshow]
interval_seconds = 30
shuffle = true
fit_mode = "fit"          # "fit" | "fill"
transition = "crossfade"  # "crossfade" | "cut" | "slide"

[display]
brightness = 72           # 0–100
show_clock = true
timezone_auto = true
timezone_region = ""      # e.g. "America/Los_Angeles"

[sleep]
enabled = false
sleep_time = "22:00"
wake_time  = "07:00"

[sync]
# OneDrive credentials and sync state managed separately
# by the existing Badger token mechanism
```

---

## 7. Nice-to-have (explicitly deferred to post-v1)

These are out of scope for the initial implementation but should not be designed
against — the architecture should not preclude adding them later.

| ID | Feature |
|---|---|
| DS-02 | Additional transition effects beyond crossfade / cut / slide |
| DS-05 | Per-photo info bar (filename, date, location) shown beneath photo |
| PB-05 | Photo metadata displayed in overlay |
| BL-05 | Ambient light auto-brightness (requires external LDR hardware) |
| WF-05 | First-run onboarding flow when no Wi-Fi is configured |
| SY-03 | Already included in v1 (device info in System section) |

---

## 8. Summary of open items for the agent

1. **Backlight privilege:** Verify whether `/sys/class/backlight/*/brightness` is
   writable by the app user, or whether a sudoers entry / small privileged helper
   process is required.

2. **Wi-Fi backend:** SSH into the target device and determine whether NetworkManager
   (`nmcli`) or `wpa_supplicant` is in use. Choose the appropriate Python binding or
   subprocess interface accordingly.

3. **Timezone manual entry UX:** If `Manual` timezone is selected, the user must type
   an IANA timezone string (e.g. `America/Los_Angeles`). The LLD should decide whether
   this is a free-text field with the on-screen keyboard, or a scrollable picker built
   from `zoneinfo`. Recommend the picker for touch usability.

4. **Vertical slider widget:** pygame has no native vertical slider. The LLD must
   specify a custom `BrightnessSlider` widget: a tall thin track, circular draggable
   thumb, value clamped 0–100, maps to 0–255 for the sysfs write.

5. **Sleep-mode tap-to-wake:** When the display is sleeping (brightness = 0), a tap
   should wake the display temporarily (restore brightness, show overlay, restart
   5-second dismiss timer). The LLD should specify how touch events are received when
   the backlight is off — verify that the touch controller remains powered.
