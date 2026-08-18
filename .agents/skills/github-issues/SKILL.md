---
name: github-issues
description: Draft, peer-review, and file GitHub issues for this repo, and look up existing ones. Use when the user asks to create or file an issue (or the /create-issue prompt runs) — it drafts the issue in .pi/tmp/ from the conversation, gets it reviewed by a technical-communication reviewer, and files it with the skill's bundled scripts/create-issue.sh. Also use when the user asks to look up an issue by number (scripts/get-issue.sh) or list issues (scripts/list-issues.sh).
---

# GitHub Issues

Issues for this repo are created and managed through the scripts bundled
with this skill (`scripts/create-issue.sh`, `scripts/get-issue.sh`) — never by
calling `gh issue` directly. This skill is the standard workflow for turning
something discussed in a conversation into a filed issue.

Paths in this skill are relative to its directory
(`.agents/skills/github-issues/`).

## When to use

- The user asks to "create/file an issue" for something discussed, or the
  `/create-issue` prompt runs.
- The user asks to look up, quote, or link an existing issue by number, or
  to list open issues.

## Filing a new issue

### 1. Draft in `.pi/tmp/`

Copy `assets/issue-template.md` to `.pi/tmp/issue-<slug>.md` and fill it in
— the repo's scratch working directory (see AGENTS.md). One file per issue.

Gather from the conversation: what happened, why it matters, where in the code
(`file:line`), and what the fix or feature should look like. If a material
detail is missing (which component, expected behaviour, severity), ask the
user one focused question before drafting — do not guess.

Deduplicate first when cheap: `bash scripts/list-issues.sh --limit 50` (open
issues by default). If an open issue already covers this, say so and stop (or
ask whether to file a duplicate anyway).

### 2. Template

Match the repo's existing conventions (see issues #34, #21, #23):

**Title** — one line, imperative, no trailing period:

| Type | Pattern | Example |
| --- | --- | --- |
| bug | `<Component>.<method>() <what is wrong> — <impact>` | `PhotoCache._key() uses path.stem — cache collision for files with the same filename stem` |
| feature | `<Component>: <what should happen>` | `Clock: add 12-hour AM/PM format option (user-selectable)` |
| engineering | `<imperative statement of the goal>` | `Achieve 90% unit test coverage across the piframe package` |
| infra | `infra: <summary>` | `infra: startup crash UX — configuration validation error reporting` |

**Body** — the template lives in `assets/issue-template.md`. Copy it to the
draft file, then:

- set the `title:` and `label:` in the leading comment (title per the table
  above),
- replace each guidance comment with the actual content,
- delete the sections that don't apply — bugs keep `## Fix direction`,
  features keep `## Current behaviour` and `## Options`, engineering keeps
  `## Implementation`.

Target 30–60 lines. If the draft is longer, it is probably two issues —
split it or ask.

### 3. Content guidance

- Write for a stranger: no "as discussed", no "we" referring to the
  conversation.
- Every code claim cites `file:line`; include a short snippet when the point
  is in the code.
- Bugs: a concrete, reproducible example beats an abstract description.
- Features: state the user-visible outcome; list design options and recommend
  one with a reason.
- One issue = one problem.
- Label: exactly one of `bug`, `feature`, `enhancement`, `engineering`, `ux`.
  The script skips labels that don't exist on the repo, so a wrong guess is
  cheap — but pick deliberately.

### 4. Peer review before filing

Run the `code-review` skill's reviewer mechanism as a **single-domain
variant**: one `reviewer` subagent, `technical-communication` domain only,
`thinking: "medium"`. (The full eight-domain review is for code changes; an
issue draft is a prose document, and only the communication domain applies.)

Spawn, then immediately block on the result:

```
Agent(
  subagent_type     = "reviewer",
  description       = "Review issue draft",
  thinking          = "medium",
  run_in_background = true,
  prompt            = <template below>
)
-> get_subagent_result(agent_id, wait = true)
```

Prompt template — fill the placeholders; the draft path must be absolute:

```
You are reviewing a GitHub issue draft for the "technical-communication" domain only.

## Document under review
Issue draft: {ABS_PATH_TO_DRAFT}
Issue title: {TITLE}

This is a prose document, not a code diff. Apply the technical-communication
checklist where it applies to prose — accuracy, actionability, terminology
consistency, spelling and grammar — and skip items that only apply to code
(docstrings, commit messages, changelogs).

## What to do
1. Read the draft file at the path above.
2. Load the `review-standards` skill, then read its technical-communication.md checklist.
3. Verify every factual claim you can: open the files the draft cites with
   read, grep, or find, and check that file:line references, quoted code, and
   described behaviour are accurate. A wrong claim in an issue is worse than a
   missing one.
4. Review only the "technical-communication" domain.

You have no shell: do not try to run git, gh, or any other command. Do not
modify any files.

Follow the required output format from the `review-standards` skill exactly.
Cite file:line for every finding — for the draft itself, cite the draft file
and its line. Your final message must end with a single VERDICT line and
nothing after it.
```

Validate the result and recover from malformed output exactly as the
`code-review` skill describes: a well-formed result has a `VERDICT:` line as
the last non-blank line plus `## REVIEW` and `## FINDINGS` sections; a
malformed result gets up to 2 `resume` attempts, then is recorded as
`INCOMPLETE` and surfaced to the user.

Act on the verdict:

| Verdict | Action |
| --- | --- |
| `APPROVE` | File the issue. |
| `APPROVE_WITH_SUGGESTIONS` | Apply the suggestions you agree with, then file. Report the rest. |
| `REQUEST_CHANGES` / `BLOCK` | Fix every blocker and major finding in the draft, re-run the review. Cap at 2 review rounds; if it still fails, show the user the draft and the open findings and let them decide. |
| `INCOMPLETE` | Show the user; do not file silently. |

### 5. File it

```bash
bash scripts/create-issue.sh --title "<title>" --body-file .pi/tmp/issue-<slug>.md --label <label>
```

`<title>` and `<label>` come from the draft's leading comment. The script
prints the issue URL — report it to the user. The draft file stays
in `.pi/tmp/` (scratch space; gitignored).

## Looking up an existing issue

```bash
bash scripts/get-issue.sh <NUMBER>
```

Use it when the user references an issue number, or when a new issue needs a
`## Related` link.

To list issues (dedup checks, finding related work):

```bash
bash scripts/list-issues.sh [--state open|closed|all] [--limit N] [--label L] [--search TEXT]
```

All the scripts pre-flight that `gh` is installed and logged in, and fail
with an actionable error otherwise — so issue management never requires the
agent to know `gh`'s own interface.
