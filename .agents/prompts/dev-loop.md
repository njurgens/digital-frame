---
description: Run the full dev loop for a GitHub issue — design doc, peer review, TDD implementation, quality gate, iterative code review, PR
argument-hint: "<issue-number>"
---
Run the dev loop for issue ${1:-the issue we just discussed} (if given as a URL,
use its trailing number).

**Setup** — all issue work happens in a feature worktree (AGENTS.md). If you are
not already in one (worktrees live at `features/<slug>` next to the main repo),
create one first: `bash eng/create-worktree.sh <issue-slug>` from the repo root,
and do all subsequent work there.

1. **Read the issue.** `bash .agents/skills/github-issues/scripts/get-issue.sh <N>`.
   Keep the title and body — they are the "task context" for every review below.

2. **Write the design doc.** Load the `design-docs` skill and author the doc at
   `docs/<issue-slug>.md` (its authoring flow, sizing table, and stable IDs apply).
   If the skill's Gate 0 says no design doc is warranted (mechanical change), say
   so and skip to step 5.

3. **Peer-review the design doc.** First run the skill's linter on the doc and fix
   mechanical issues. Then, using the `code-review` skill's reviewer mechanism
   (spawn in background, immediately block on `get_subagent_result(wait=true)`,
   validate the result, recover malformed output with up to 2 `resume` attempts),
   run two `reviewer` subagents **sequentially**, both with `thinking: "medium"`:
   first the `architecture` domain, then `technical-communication`, using the
   design-doc reviewer prompt in the next section.

4. **Iterate — up to 2 fix-and-re-review rounds.** Fix every blocker/major
   finding (apply minor/nit as you see fit), then re-run **only the domains that
   did not pass** — never re-run a domain that already passed. If a domain still
   fails after 2 rounds, show the user the doc and the open findings and let them
   decide. An `INCOMPLETE` domain is surfaced, never silently passed.

5. **Implement (TDD).** Implement the design doc test-first: for each behavior,
   write a failing test first, then the minimum code to pass it, keeping the test
   suite green as you go (the full gate is step 6). Follow the `modern-python`
   skill for all Python. Commit in logical increments, each with a
   `Co-Authored-By:` line (AGENTS.md convention).

6. **Quality gate.** Run `bash eng/test.sh` (90% diff-coverage gate),
   `bash eng/format.sh`, and `bash eng/check.sh`; fix and re-run until all three
   are clean.

7. **Full code review — iterative, per-domain.** Load the `code-review` skill.
   Run its Step 0 (`bash .agents/skills/code-review/scripts/make-review-diff.sh`
   from the repo root; capture the KEY=VALUE block), then walk its eight domains
   in the fixed order, one reviewer at a time, using its prompt template (change
   summary + the issue as task context + the artifact paths; the diff includes
   the design doc). **Iteration rule (overrides the skill's "re-run all eight"):**
   if a domain returns REQUEST_CHANGES or BLOCK, fix every blocker and major
   finding, commit, re-run `make-review-diff.sh` to regenerate the artifacts, and
   re-run **only that domain's** reviewer; repeat until it passes (APPROVE or
   APPROVE_WITH_SUGGESTIONS — apply the suggestions you agree with). **Never
   re-run a domain that has already passed**, even if a later fix touches the same
   files. If a domain still fails after 3 fix cycles, stop and show the user the
   open findings.

8. **Open the PR.** Commit everything (design doc + code, `Co-Authored-By:`
   line). Write the PR body to `.pi/tmp/pr-<issue-slug>.md` — what changed,
   `Fixes #<N>`, the design doc path, and the review outcome — then:
   `bash eng/create-pr.sh --title "<title>" --body-file .pi/tmp/pr-<issue-slug>.md`
   Report the PR URL.

## Design-doc reviewer prompt

Fill this in for each of the two domains and pass it as the `Agent` tool's
`prompt`. Copy it exactly; only replace the `{...}` placeholders.

```
You are reviewing a design doc for the "{domain}" domain only.

## Document under review
Design doc: {DOC_PATH}
Issue: #{ISSUE_NUMBER} — {ISSUE_TITLE}

This is a prose design document, not a code diff. Apply the {domain} checklist
where it applies to a design argument and skip items that only apply to code.

## Task context
{TASK_CONTEXT}

## What to do
1. Read the design doc at the path above.
2. Load the `review-standards` skill, then read its {domain}.md checklist.
3. Review only the "{domain}" domain, using that checklist.

Open any file you need for context with read, grep, or find. You have no shell:
do not try to run git, the linter, or any other command. Do not modify any files.

Follow the required output format from the `review-standards` skill exactly.
Cite file:line for every finding — for the doc itself, cite the doc file and its
line. Your final message must end with a single VERDICT line and nothing after it.
```

Placeholder rules:

- `{domain}` — `architecture` or `technical-communication`, spelled exactly.
- `{DOC_PATH}` — absolute path to the design doc.
- `{ISSUE_NUMBER}` / `{ISSUE_TITLE}` — from step 1.
- `{TASK_CONTEXT}` — the issue body, verbatim where possible.
