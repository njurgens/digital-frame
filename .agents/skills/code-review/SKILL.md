---
name: code-review
description: Runs a multi-round peer review of a finished code change by spawning the `reviewer` subagent once per domain — architecture, correctness, testing, backwards-compatibility, security, performance, code-style, technical-communication — strictly one at a time, then aggregating the eight verdicts into a single pass/fail decision. Use this after writing or coordinating a code change and before calling it done, whenever a change needs review, sign-off, or a quality gate. Includes the exact Agent / get_subagent_result call sequence and the recovery procedure for when the local model fails to emit a tool call.
---

# Peer Review Orchestration

You just produced (or are coordinating) a code change. Before the change is
considered done, it gets reviewed by eight peer reviewers, each looking at one
domain. This skill tells you exactly how to run them.

You are the orchestrator. You do not review anything yourself. You spawn
reviewers, collect their structured results, and aggregate.

## When to run this

- A code change is complete and ready for review.
- Before the change is marked done, merged, or handed to the next dev-loop stage.

Do not run peer review on a work-in-progress change. Finish the change first.

## Step 0 — generate the review artifacts first

Reviewers have **no shell**. They cannot run `git diff`, `git log`, the tests, or
anything else. They can only open files with `read`, `grep`, and `find`. So
everything they need must exist as a file before the first reviewer is spawned,
and it is your job to produce it.

Run this once, before spawning any reviewer:

```
./scripts/make-review-diff.sh
```

It diffs the working tree against the **merge base** with the parent branch — not
against the branch tip — so the reviewers see only what this change did, not
whatever else landed on `main` in the meantime. Pass `--base <ref>` if the parent
branch is not `main`.

It prints a `KEY=VALUE` block. Capture these values; you will paste them into
every reviewer prompt:

```
REPO_ROOT=/path/to/repo
BASE_REF=main
MERGE_BASE=<sha>
DIFF_FILE=/path/to/.pi/tmp/peer-review/review.diff
CHANGED_FILES_FILE=/path/to/.pi/tmp/peer-review/changed-files.txt
COMMITS_FILE=/path/to/.pi/tmp/peer-review/commits.txt
DIFFSTAT_FILE=/path/to/.pi/tmp/peer-review/diffstat.txt
FILES_CHANGED=7
DIFF_LINES=412
COMMIT_COUNT=3
UNTRACKED_INCLUDED=1
UNTRACKED_SKIPPED=0
STATUS=OK
```

Before spawning anything, check the output:

- `STATUS=EMPTY` (exit code 2) — there is no change to review. Stop. Do not spawn
  reviewers against an empty diff; eight reviewers will each invent findings out
  of nothing. Tell the user there is nothing to review.
- Exit code 1 — the script failed and printed why (not a git repo, base ref not
  found). Fix that before continuing.
- `UNTRACKED_SKIPPED` greater than 0 — one or more new files were too large to
  inline. Note them in the final report under "Not reviewed".

Options, if you need them:

| Option | Effect |
| --- | --- |
| `--base <ref>` | Diff against a parent branch other than `main`. |
| `--out-dir <dir>` | Write artifacts somewhere other than `.pi/tmp/peer-review`. |
| `--committed` | Diff only committed work. Default also includes staged and unstaged changes. |
| `--no-untracked` | Do not inline new untracked files. Use only if you know they are irrelevant. |

By default the script includes **untracked files**. This matters: a brand-new
file the author never staged is invisible to `git diff`, and without this every
reviewer would silently review the change with its most important file missing.

The script writes a `.gitignore` into the artifact directory so that the next
review round does not diff the previous round's output.

Do not hand-roll the diff with your own `git` invocation. Diffing against the
branch tip instead of the merge base is the usual mistake, and it silently feeds
reviewers unrelated commits from `main`.

## The eight domains — fixed order

Run them in exactly this order. Do not reorder, skip, or add domains.

1. `architecture`
2. `correctness`
3. `testing`
4. `backwards-compatibility`
5. `security`
6. `performance`
7. `code-style`
8. `technical-communication`

All eight use the same subagent type: `reviewer`. The domain is passed in the
prompt, not by picking a different agent.

## Execution model — one reviewer at a time

**Run reviewers strictly sequentially.** Spawn one, wait for it to finish, then
spawn the next. Never have two reviewers running at once.

This project runs a single locally-hosted Qwen3.6-27B model. Running reviewers
concurrently — which is what pi-subagents does by default — overloads that one
model and degrades every review at once. Sequencing is deliberate.

The pattern is: spawn in background mode, then immediately block on the result.

```
Run make-review-diff.sh once (Step 0). Capture the KEY=VALUE block.

FOR each domain in the fixed order above:
    1. Agent(
           subagent_type = "reviewer",
           description   = "Review <domain>",
           prompt        = <the filled-in template below>,
           run_in_background = true
       )
       -> returns an agent_id

    2. get_subagent_result(agent_id = <that agent_id>, wait = true)
       -> blocks until this reviewer is done

    3. Validate the result (see "Validating a result").
       If malformed, run the recovery procedure before moving on.

    4. Record: domain, agent_id, verdict, findings, scope notes.

    5. Only now move to the next domain.
```

`run_in_background: true` followed immediately by a blocking
`get_subagent_result(agent_id, wait=true)` gives you background mode's
notification and telemetry behavior while still enforcing strict one-at-a-time
sequencing.

**Do not spawn the next reviewer until the current one has returned a result.**
If you find yourself with two `agent_id`s that have not both been resolved, you
have made a mistake — stop and resolve the outstanding one.

## The prompt template

Fill this in for each domain and pass it as the `Agent` tool's `prompt`. Copy it
exactly; only replace the `{...}` placeholders.

```
You are reviewing a code change for the "{domain}" domain only.

## Change summary
{change_summary}

## Task context
{original_task_description}

## Where to find the change
Diff file:          {DIFF_FILE}
Changed files list: {CHANGED_FILES_FILE}
Commit messages:    {COMMITS_FILE}
Diff summary:       {DIFFSTAT_FILE}
Repository root:    {REPO_ROOT}

The diff is against the merge base {MERGE_BASE} with branch {BASE_REF}.

## What to do
1. Read the diff file at the path above.
2. Load the `review-standards` skill, then read its {domain}.md checklist.
3. Review only the "{domain}" domain, using that checklist.

Open any file you need for context with read, grep, or find. You have no shell:
do not try to run git, the tests, or any other command. If you need something you
cannot open, record it under NOT_REVIEWED.

Do not comment on other domains — they have their own reviewers. Do not modify
any files.

Follow the required output format from the `review-standards` skill
exactly. Cite file:line for every finding. Your final message must end with a
single VERDICT line and nothing after it.
```

Placeholder rules:

- `{domain}` — one of the eight names, spelled exactly as listed above,
  lowercase with hyphens.
- `{change_summary}` — 2–5 sentences: what the change does and why.
- `{original_task_description}` — the task the change was supposed to
  accomplish, verbatim where possible. Reviewers need this to judge whether the
  change did what was asked.
- The five path values come straight from the `KEY=VALUE` block that
  `make-review-diff.sh` printed in Step 0. Paste them unchanged. They are
  absolute paths, so they work regardless of the reviewer's working directory.
- Do **not** inline the diff text into the prompt. It goes in the file. A large
  diff pasted into the prompt eight times wastes most of the local model's
  context before it has read anything.

Set `description` on the `Agent` call to `"Review <domain>"` — e.g.
`"Review security"`. Keep it short; it is a label, not the prompt.

## Validating a result

A result is **well-formed** when all of these hold:

1. It is non-empty.
2. It contains a line matching `VERDICT: X` where X is exactly one of
   `APPROVE`, `APPROVE_WITH_SUGGESTIONS`, `REQUEST_CHANGES`, `BLOCK`.
3. That `VERDICT:` line is the last non-blank line.
4. It contains a `## REVIEW` section and a `## FINDINGS` section.

If any of these fail, the result is **malformed**. Treat a malformed result as a
tooling failure, not as a review outcome. Do not guess a verdict on the
reviewer's behalf, and do not treat a missing verdict as an approval.

## Known idiosyncrasy: the local model sometimes does not emit a tool call

The local Qwen3.6-27B model intermittently ends a turn without emitting the tool
call or the final structured message it was asked for. You will see this as:

- an empty result,
- plain conversational text instead of the review format ("Sure, I'll review
  that now."),
- a review that stops partway with no `VERDICT:` line,
- an agent whose status is `completed` or `steered` but whose output does not
  follow the format.

This is a model failure, not a reviewer judgment. **Resume the same session
rather than spawning a fresh reviewer** — the resumed session still has the diff
and whatever it already read, so it is both cheaper and more likely to produce a
usable review than starting over.

### Recovery procedure

When `get_subagent_result(agent_id, wait=true)` returns and the result is
malformed:

1. Call the `Agent` tool with the **`resume`** parameter set to that agent's
   `agent_id`, `subagent_type: "reviewer"`, `run_in_background: true`, a
   `description` like `"Resume review <domain>"`, and this nudge prompt:

   ```
   You did not produce a completed review in the required format. Continue now
   and output your review using the exact format from the review-standards
   skill, ending with a VERDICT line. Do not restart the review. Do not modify
   any files.
   ```

2. Immediately call `get_subagent_result(agent_id, wait=true)` again and
   re-validate.

3. **Cap this at 2 resume attempts per domain.** If the result is still
   malformed after the second resume, stop retrying that domain. Record it as:

   ```
   DOMAIN: <domain>
   VERDICT: INCOMPLETE
   NOTE: reviewer did not produce a well-formed review after 2 resume attempts (agent_id: <id>)
   ```

   Then move on to the next domain. One stuck reviewer must not stall the other
   seven.

Notes on `resume`:

- `resume` continues an existing session. It is for a session that has ended or
  stalled.
- `resume` **cannot be combined with `schedule`.**
- Fields pinned in the agent's frontmatter (such as `model`) stay authoritative
  across a resume — you cannot override them on the resuming call, and you
  should not try.
- If a reviewer is still *running* and you need to redirect it mid-task, that is
  `steer_subagent(agent_id, message)`, not `resume`. In this workflow you almost
  never need it, because you block on the result immediately after spawning.

`INCOMPLETE` is a process outcome, not a review verdict. It never counts as an
approval. If any domain is `INCOMPLETE`, say so prominently in the summary so a
human knows that domain went unreviewed.

## Aggregating the eight results

Once all eight domains have a recorded outcome, apply this in order and stop at
the first match:

| Condition | Decision | What to do |
| --- | --- | --- |
| Any domain returned `BLOCK` | **FAIL — stop** | Do not proceed. Fix every `blocker` finding, then re-run peer review from domain 1. |
| Any domain returned `REQUEST_CHANGES` | **FAIL — fix first** | Address every `blocker` and `major` finding, then re-run peer review from domain 1. |
| Any domain is `INCOMPLETE` | **HOLD** | Report which domains went unreviewed and ask the user whether to proceed or retry those domains. Do not silently pass. |
| All domains `APPROVE` or `APPROVE_WITH_SUGGESTIONS` | **PASS** | Proceed to the next dev-loop stage. Report the suggestions; the author may fix or decline them. |

Re-running after fixes means re-running `make-review-diff.sh` to regenerate the
diff, then running all eight domains again in order — not just the domains that
failed. Regenerating is not optional: reviewers given a stale diff file will
report findings the author already fixed. And re-running all eight matters
because a fix can break another domain.

## Reporting back

Present the aggregate like this:

```
# Peer review: <change summary line>

DECISION: PASS | FAIL | HOLD

| Domain | Verdict | Blockers | Majors | Minors | Nits |
| --- | --- | --- | --- | --- | --- |
| architecture | APPROVE | 0 | 0 | 0 | 0 |
| correctness | REQUEST_CHANGES | 0 | 2 | 1 | 0 |
| ... | | | | | |

## Must fix before proceeding
- [correctness] src/api/client.py:88 — <issue> → <fix>
- [security] src/reports/query.py:57 — <issue> → <fix>

## Optional
- [code-style] src/jobs/scheduler.py:38 — <issue> → <fix>

## Not reviewed
- <domain>: <why> (or "nothing")
```

Order the "Must fix" list by severity: all `blocker` findings first, then all
`major`. Keep each line to one line. Do not paste the eight full reviews into the
summary — keep the raw reviews available, but lead with the table and the
must-fix list.

## Tool reference

These are the pi-subagents tools this skill uses. Use only these parameters.

**`Agent`** — spawn or resume a subagent.

```js
// Spawn a new reviewer for a single domain
Agent({
  subagent_type: "reviewer",
  description: "Review security",
  run_in_background: true,
  prompt: `You are reviewing a code change for the "security" domain only.

## Change summary
{change_summary}

## Task context
{original_task_description}

## Where to find the change
Diff file:          /path/to/.pi/tmp/peer-review/review.diff
Changed files list: /path/to/.pi/tmp/peer-review/changed-files.txt
Commit messages:    /path/to/.pi/tmp/peer-review/commits.txt
Diff summary:       /path/to/.pi/tmp/peer-review/diffstat.txt
Repository root:    /path/to/repo

The diff is against the merge base abc123 with branch main.

## What to do
1. Read the diff file at the path above.
2. Load the `review-standards` skill, then read its security.md checklist.
3. Review only the "security" domain, using that checklist.

Open any file you need for context with read, grep, or find. You have no shell:
do not try to run git, the tests, or any other command. If you need something you
cannot open, record it under NOT_REVIEWED.

Do not comment on other domains — they have their own reviewers. Do not modify
any files.

Follow the required output format from the `review-standards` skill
exactly. Cite file:line for every finding. Your final message must end with a
single VERDICT line and nothing after it.`
});
```

```js
// Resume a stalled reviewer (malformed-output recovery)
Agent({
  subagent_type: "reviewer",
  description: "Resume review security",
  resume: "agent-abc123",
  run_in_background: true,
  prompt: `You did not produce a completed review in the required format. Continue now
and output your review using the exact format from the review-standards
skill, ending with a VERDICT line. Do not restart the review. Do not modify
any files.`
});
```

**`get_subagent_result`** — collect a subagent's result.

```js
// Block until the reviewer finishes (enforces sequencing)
get_subagent_result({
  agent_id: "agent-abc123",
  wait: true,
});
```

```js
// Diagnose a malformed result — include the full transcript
get_subagent_result({
  agent_id: "agent-abc123",
  wait: true,
  verbose: true,
});
```

**`make-review-diff.sh`** — produce the artifacts reviewers read. Run once, in
Step 0, before any reviewer is spawned.

```bash
# Default: diff against main, include untracked files
./scripts/make-review-diff.sh
```

```bash
# Diff against a different parent branch
./scripts/make-review-diff.sh --base develop
```

```bash
# Committed-only, skip untracked, custom output directory
./scripts/make-review-diff.sh --base main --committed --no-untracked --out-dir .pi/tmp/custom-review
```

Options:

| Option | Default | Notes |
| --- | --- | --- |
| `--base <ref>` | `main`, else `origin/main`, `master`, `origin/master` | Parent branch. Diffs against the merge base with it. |
| `--out-dir <dir>` | `.pi/tmp/peer-review` | Absolute or relative; reported paths are always absolute. |
| `--committed` | off | Restrict to committed work only. |
| `--no-untracked` | off | Skip new untracked files. |

Exit codes: `0` artifacts written, `1` error (message on stderr), `2` nothing to
review.

**`steer_subagent`** — redirect a subagent that is still running.

```js
steer_subagent({
  agent_id: "agent-abc123",
  message: "Focus on the authentication flow in src/auth/ — the diff file covers lines 1-200.",
});
```

Parameters:

| Parameter | Type | Notes |
| --- | --- | --- |
| `agent_id` | string | **Required.** |
| `message` | string | **Required.** The redirection. |

`steer_subagent` is for a live agent; `resume` is for one whose session has
ended or stalled. Do not use `steer_subagent` for the malformed-output recovery
above — by then the agent is no longer running.

## Checklist before you report

- [ ] `make-review-diff.sh` ran successfully and `STATUS=OK`.
- [ ] Every reviewer prompt carried the absolute artifact paths from Step 0.
- [ ] All eight domains were spawned, in the fixed order.
- [ ] Each was spawned only after the previous one returned a result.
- [ ] Each result was validated for a well-formed `VERDICT:` line.
- [ ] Any malformed result got at most 2 `resume` attempts, then `INCOMPLETE`.
- [ ] The aggregate decision follows the table above, not your own judgment.
- [ ] `INCOMPLETE` domains are named explicitly in the report.
