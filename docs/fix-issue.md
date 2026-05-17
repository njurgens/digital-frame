# Fix Issue — Agent Prompt

> **Usage:** Paste this prompt into a Copilot / Claude Code session, substituting the real issue number for `$ISSUE`.
> Example: "Fix GitHub issue #12 following docs/fix-issue.md."

---

## Your task

Fix GitHub issue **#$ISSUE** in the `njurgens/digital-frame` repository from start to merged PR, following every step below in order. Do not skip steps. Do not open a PR until the review gauntlet is complete.

---

## Step 1 — Understand the issue

```bash
gh issue view $ISSUE --repo njurgens/digital-frame
```

Read the full issue body. Identify:
- What is broken or missing?
- Which files are involved (the issue body usually names them with line numbers)?
- What is the acceptance criterion — how will you know the fix is correct?

If the issue is ambiguous, state your interpretation before proceeding.

---

## Step 2 — Read the relevant design documents

Before writing a single line of code, read the sections of the design docs that govern the affected area:

| Doc | What it covers |
|-----|----------------|
| `docs/pi-frame-ux-requirements.md` | All observable UX behaviour — the source of truth for what the frame must do |
| `docs/pi-frame-hld.md` | Component boundaries, state machine, data flow |
| `docs/pi-frame-lld.md` | Widget specs, layout constants, rendering contracts |

Identify every requirement that the issue touches. Write a one-paragraph **Design Note** (in your working notes, not in a file) describing how your fix satisfies each requirement without breaking others.

---

## Step 3 — Create a worktree and branch

All issue work must be done in a dedicated git worktree (see `AGENTS.md §Working in Git Worktrees`). This keeps the main checkout clean and lets multiple issues run in parallel.

```bash
# Run from the repo root:
git pull
git worktree add ../digital-frame-issue-$ISSUE -b fix/issue-$ISSUE-<slug>
# e.g.
git worktree add ../digital-frame-issue-13 -b fix/issue-13-nav-icon-alignment

cd ../digital-frame-issue-$ISSUE
```

Do all subsequent work — edits, test runs, commits — inside the worktree directory. Point review-round sub-agents at this path. After the PR is merged, clean up:

```bash
git worktree remove ../digital-frame-issue-$ISSUE
```

---

## Step 4 — Implement the fix

Follow the project conventions in `AGENTS.md` and `CLAUDE.md`:

- **No venv, no pip.** All Python dependencies must be `apt` packages.
- **No comments** unless the WHY is non-obvious.
- **No new files** unless the design clearly requires them (e.g. a new widget or interface).
- **No scope creep.** Fix exactly what the issue describes; leave unrelated improvements for their own issues.
- If the fix touches `clock_widget.py` or any caching path, **bump `_CACHE_VERSION`** in `photo_cache.py`.
- If the fix touches `eng/install.sh`, keep the bash heredoc free of Python raw strings and backslash sequences (the heredoc is unquoted — bash mangles them).

After implementing, run the unit tests locally to establish a baseline:

```bash
cd /home/nick/src/digital-frame
python3 -m pytest tests/ -x -q 2>&1 | tail -20
```

All pre-existing tests must remain green.

---

## Step 5 — Write or update tests

Every fix needs test coverage. Choose the right tier:

| Fix type | Test tier |
|----------|-----------|
| Pure logic change (config, scheduler, widget state) | Unit test in `tests/` |
| New widget or rendering path | Unit render test in `tests/test_widget_renders.py` |
| OS-boundary class (backlight, nmcli, updater) | Unit test via thin mock — **no real hardware calls** |
| Wi-Fi connect flow | Unit test via `MockWifiManager` — **must not call `nmcli connect`** |

Rules:
- The OS-boundary rule is absolute: **integration tests must not actually connect to Wi-Fi** — it will drop the SSH session used by the test harness.
- Aim for ≥ 90 % line coverage on every file you touch. Check with:
  ```bash
  python3 -m pytest tests/ --cov=piframe --cov-report=term-missing -q 2>&1 | tail -30
  ```
- Tests must pass on the dev machine (Linux/WSL, no Pi required for unit tests).

---

## Step 6 — Run the review gauntlet

Run all five rounds in order. **Do not advance to the next round while the current reviewer is `BLOCKED`.** Resolve every Critical, High, and Medium finding, then re-run the same reviewer until it signs off.

### Round 1 — Architecture

```
Agent(subagent_type="review-architecture",
      prompt="Review the changes on branch fix/issue-$ISSUE-<slug> against
              docs/pi-frame-ux-requirements.md, docs/pi-frame-hld.md, and
              docs/pi-frame-lld.md. Changed files: <list changed files>.
              Produce the structured Architecture Review report.")
```

Sign-off required: `APPROVED` or `APPROVED WITH NOTES`.

### Round 2 — Correctness

```
Agent(subagent_type="review-correctness",
      prompt="Review the changes on branch fix/issue-$ISSUE-<slug> for
              implementation correctness — logic errors, edge cases, concurrency,
              resource leaks. Changed files: <list>. Produce the structured
              Correctness Review report.")
```

### Round 3 — Security

```
Agent(subagent_type="review-security",
      prompt="Review the changes on branch fix/issue-$ISSUE-<slug> for security
              issues — credential handling, subprocess injection, path traversal,
              secure defaults. Changed files: <list>. Produce the structured
              Security Review report.")
```

### Round 4 — Docs

```
Agent(subagent_type="review-docs",
      prompt="Review the changes on branch fix/issue-$ISSUE-<slug> for
              documentation accuracy — design docs, comments, config examples.
              Changed files: <list>. Produce the structured Documentation
              Review report.")
```

### Round 5 — Testing

```
Agent(subagent_type="review-testing",
      prompt="Review the changes on branch fix/issue-$ISSUE-<slug> for test
              coverage and requirement mapping. Changed files: <list>. Produce
              the structured Testing Review report.")
```

---

## Step 7 — Final checks

Before opening the PR:

```bash
# All tests green
python3 -m pytest tests/ -x -q

# Coverage ≥ 90% on touched files
python3 -m pytest tests/ --cov=piframe --cov-report=term-missing -q

# No uncommitted changes
git status
```

---

## Step 8 — Open the pull request

```bash
git push -u origin fix/issue-$ISSUE-<slug>

gh pr create \
  --repo njurgens/digital-frame \
  --title "<verb>: <short description> (fixes #$ISSUE)" \
  --body "$(cat <<'EOF'
## Summary

- <bullet: what changed and why>
- <bullet: which files were touched>
- <bullet: any non-obvious decision made>

## Fixes

Closes #$ISSUE

## Test plan

- [ ] `python3 -m pytest tests/ -x -q` — all green
- [ ] Coverage ≥ 90% on touched modules
- [ ] Five-round review gauntlet: all rounds APPROVED
- [ ] <any manual verification step specific to this fix, e.g. "deploy to Pi and confirm overlay buttons render correctly">

## Review gauntlet

| Round | Reviewer | Result |
|-------|----------|--------|
| 1 | review-architecture | APPROVED / APPROVED WITH NOTES |
| 2 | review-correctness  | APPROVED / APPROVED WITH NOTES |
| 3 | review-security     | APPROVED / APPROVED WITH NOTES |
| 4 | review-docs         | APPROVED / APPROVED WITH NOTES |
| 5 | review-testing      | APPROVED / APPROVED WITH NOTES |
EOF
)"
```

The PR body must include the gauntlet table with actual results. Do not leave placeholder text.
