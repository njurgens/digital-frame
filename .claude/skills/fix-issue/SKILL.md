---
name: fix-issue
description: >
  Full SDLC workflow for fixing a GitHub issue in the Pi Frame project: read the
  issue, design against the spec docs, branch, implement, write tests, run the
  five-round review gauntlet, and open a pull request. Use this skill whenever
  the user mentions fixing, closing, implementing, or working on a GitHub issue —
  especially when an issue number appears (e.g. "#12", "issue 5", "fix the overlay
  bug"). Also use it when the user says "pick up an issue", "work on a ticket", or
  "start on #N". Do not wait for the user to say the word "skill".
---

# Fix Issue

You are working in the **Pi Frame** repository (`njurgens/digital-frame`).
Follow every step below in order. Do not open a PR until the review gauntlet
is complete.

## Step 1 — Read the issue

```bash
gh issue view $ISSUE --repo njurgens/digital-frame
```

Identify:
- What is broken or missing?
- Which files are involved (the issue usually names them)?
- What does "fixed" look like — how will you verify it?

State your interpretation of the acceptance criterion before proceeding.

## Step 2 — Read the relevant design docs

Before writing any code, read the sections that govern the affected area:

| Doc | Covers |
|-----|--------|
| `docs/pi-frame-ux-requirements.md` | All observable UX behaviour — source of truth |
| `docs/pi-frame-hld.md` | Component boundaries, state machine, data flow |
| `docs/pi-frame-lld.md` | Widget specs, layout constants, rendering contracts |

Write a one-paragraph **Design Note** in your reasoning that explains how your
fix satisfies every touched requirement without breaking others.

## Step 3 — Create a worktree and branch

All issue work happens in a dedicated git worktree so the main checkout stays
clean and multiple issues can run in parallel.

```bash
# Run from the repo root (main checkout):
git pull
git worktree add ../digital-frame-issue-$ISSUE -b fix/issue-$ISSUE-<slug>
# e.g.
git worktree add ../digital-frame-issue-13 -b fix/issue-13-nav-icon-alignment

cd ../digital-frame-issue-$ISSUE
```

Do all subsequent work (edit, test, commit) inside the worktree directory.
Point review-round sub-agents at this path, not at the main checkout.

## Step 4 — Implement the fix

Project constraints (from `CLAUDE.md`):

- **No venv, no pip.** All Python deps must be `apt` packages.
- **No comments** unless the WHY is non-obvious (a hidden constraint, a subtle
  invariant, a workaround for a specific bug).
- **No scope creep.** Fix exactly what the issue describes.
- If the fix touches `clock_widget.py` or any rendering/cache path, **bump
  `_CACHE_VERSION`** in `photo_cache.py`.
- If the fix touches `eng/install.sh`, keep the bash heredoc free of Python raw
  strings and backslash sequences — the heredoc is unquoted and bash mangles them.
- When launching or killing the slideshow over SSH, **never use `pkill -f` or
  `pgrep -f`** — the `-f` flag matches the SSH command itself and hangs the session.

After implementing, verify the pre-existing tests still pass:

```bash
python3 -m pytest tests/ -x -q 2>&1 | tail -20
```

## Step 5 — Write or update tests

| Fix type | Test tier |
|----------|-----------|
| Pure logic (config, scheduler, widget state) | Unit test in `tests/` |
| New widget or rendering path | Render test in `tests/test_widget_renders.py` |
| OS-boundary class (backlight, nmcli, updater) | Unit test via thin mock — **no real hardware calls** |
| Wi-Fi connect flow | Unit test via `MockWifiManager` — **must not call `nmcli connect`** |

The no-real-nmcli-connect rule is absolute: actually connecting to Wi-Fi over
the test SSH session will drop the connection.

Target ≥ 90% line coverage on every file you touch:

```bash
python3 -m pytest tests/ --cov=piframe --cov-report=term-missing -q 2>&1 | tail -30
```

## Step 6 — Run the five-round review gauntlet

Run rounds in order. **Do not advance while the current reviewer is `BLOCKED`.**
Resolve every Critical, High, and Medium finding, then re-run the same reviewer
until it signs off (`APPROVED` or `APPROVED WITH NOTES`).

Spawn each reviewer like this (substitute the real branch name and file list):

```
# Round 1 — Architecture (always first)
Agent(subagent_type="review-architecture",
      prompt="Review branch fix/issue-$ISSUE-<slug> against
              docs/pi-frame-ux-requirements.md, docs/pi-frame-hld.md, and
              docs/pi-frame-lld.md. Changed files: <list>.
              Produce the structured Architecture Review report.")

# Round 2 — Correctness
Agent(subagent_type="review-correctness",
      prompt="Review branch fix/issue-$ISSUE-<slug> for implementation
              correctness — logic errors, edge cases, concurrency, resource
              leaks. Changed files: <list>.
              Produce the structured Correctness Review report.")

# Round 3 — Security
Agent(subagent_type="review-security",
      prompt="Review branch fix/issue-$ISSUE-<slug> for security issues —
              credential handling, subprocess injection, path traversal, secure
              defaults. Changed files: <list>.
              Produce the structured Security Review report.")

# Round 4 — Docs
Agent(subagent_type="review-docs",
      prompt="Review branch fix/issue-$ISSUE-<slug> for documentation
              accuracy — design docs, comments, config examples.
              Changed files: <list>.
              Produce the structured Documentation Review report.")

# Round 5 — Testing
Agent(subagent_type="review-testing",
      prompt="Review branch fix/issue-$ISSUE-<slug> for test coverage and
              requirement mapping. Changed files: <list>.
              Produce the structured Testing Review report.")
```

## Step 7 — Final checks

```bash
python3 -m pytest tests/ -x -q          # all green
python3 -m pytest tests/ --cov=piframe --cov-report=term-missing -q   # ≥ 90%
git status                               # nothing uncommitted
```

## Step 8 — Open the pull request

```bash
git push -u origin fix/issue-$ISSUE-<slug>

gh pr create \
  --repo njurgens/digital-frame \
  --title "<verb>: <short description> (fixes #$ISSUE)" \
  --body "$(cat <<'EOF'
## Summary

- <what changed and why>
- <which files were touched>
- <any non-obvious decision>

## Fixes

Closes #$ISSUE

## Test plan

- [ ] `python3 -m pytest tests/ -x -q` — all green
- [ ] Coverage ≥ 90% on touched modules
- [ ] Five-round review gauntlet complete (see table below)
- [ ] <manual verification step specific to this fix>

## Review gauntlet

| Round | Reviewer | Result |
|-------|----------|--------|
| 1 | review-architecture | <!-- APPROVED / APPROVED WITH NOTES --> |
| 2 | review-correctness  | <!-- APPROVED / APPROVED WITH NOTES --> |
| 3 | review-security     | <!-- APPROVED / APPROVED WITH NOTES --> |
| 4 | review-docs         | <!-- APPROVED / APPROVED WITH NOTES --> |
| 5 | review-testing      | <!-- APPROVED / APPROVED WITH NOTES --> |
EOF
)"
```

Fill in the gauntlet table with actual results before submitting.
