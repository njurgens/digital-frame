---
name: rubber-duck
description: Adversarial peer review of a finished artifact — spec, requirements, code, plan, task, doc.
---

# Rubber Duck Review

Spawn the `rubber-duck` subagent to attack an artifact and report defects. It does not fix anything. You fix.

## When to run

- An artifact is finished and something downstream will act on it.
- Before merge, handoff, or execution.
- After you fix findings, to re-check.

## When not to run

- The artifact is still being drafted. Review of a moving target wastes both agents.
- You want it rewritten or improved. The duck does not write.
- Throwaway output nothing depends on.

## Rules

1. Never set `inherit_context: true`. A duck that sees your reasoning reviews your reasoning instead of the artifact, and agrees with you. Independence is the whole value.
2. Never use `resume` for a re-review. Spawn a fresh agent, for the same reason.
3. If the artifact is on disk, pass the path. The duck has `read`, `grep`, `find`, `ls`, and pasting a large artifact into `prompt` burns context it needs for the review.
4. If the artifact is not on disk, write it to a file first, then pass the path.
5. Always fill CONTEXT with the original request and the constraints. Without it the duck can check whether the artifact is internally sound but not whether it answers the right question — usually the more expensive defect.
6. Do not argue findings back. Fix, or escalate to the user.
7. Stop after 3 rounds. Persistent disagreement past that usually means the original request was underspecified, and more review will not fix that.

## Prompt template

Fill every field. Write `unknown` if you truly do not know — a wrong guess is worse than an admitted gap.

```
ARTIFACT_TYPE: <what it is>
DOWNSTREAM_CONSUMER: <who or what acts on this next>

CONTEXT
Original request: <the task that produced the artifact>
Constraints: <standards, prior decisions, non-goals>
Related: <paths to upstream artifacts>

ARTIFACT
File: <path>
```

## Usage

### 1. Review one artifact (blocking)

The default. Use it when you cannot proceed until the review is back.

```js
Agent({
  subagent_type: "rubber-duck",
  description: "Review auth design spec",
  prompt: `ARTIFACT_TYPE: design spec
DOWNSTREAM_CONSUMER: implementation agent

CONTEXT
Original request: Add SSO login for enterprise tenants.
Constraints: Must reuse existing session store. No new external deps.
Related: docs/decisions/0012-session-store.md

ARTIFACT
File: docs/design/auth-sso.md`,
})
```

### 2. Review several artifacts in parallel

One duck reviews one artifact. Splitting them keeps each review focused and lets you act on whichever comes back first.

```js
Agent({
  subagent_type: "rubber-duck",
  description: "Review API schema",
  prompt: `ARTIFACT_TYPE: openapi schema
DOWNSTREAM_CONSUMER: client codegen

CONTEXT
Original request: Expose tenant admin endpoints.
Constraints: Must match docs/design/auth-sso.md.

ARTIFACT
File: api/openapi.yaml`,
  run_in_background: true,
})

Agent({
  subagent_type: "rubber-duck",
  description: "Review migration plan",
  prompt: `ARTIFACT_TYPE: migration plan
DOWNSTREAM_CONSUMER: ops engineer

CONTEXT
Original request: Move sessions to the new store.
Constraints: Zero downtime. Rollback required.

ARTIFACT
File: docs/plans/session-migration.md`,
  run_in_background: true,
})
```

Each call returns an `agent_id`. Collect results:

```js
get_subagent_result({ agent_id: "<id from spawn>", wait: true })
```

Add `verbose: true` to see the duck's full reasoning instead of just the report:

```js
get_subagent_result({ agent_id: "<id>", wait: true, verbose: true })
```

### 3. Correct a running duck
 
Only when it drifts — rewriting the artifact, reviewing the wrong file, failing tool calls, stalling, or failing to produce a report. Not for disputing findings.
 
```js
steer_subagent({
  agent_id: "<id>",
  message: "Do not propose fixes. Report the defect and the condition that closes it.",
})
```

### 3. Re-review after fixes

New spawn, not `resume`. Say which round it is and what changed, so the duck spends its turns on the changed parts.

```js
Agent({
  subagent_type: "rubber-duck",
  description: "Re-review auth design spec",
  prompt: `ARTIFACT_TYPE: design spec
DOWNSTREAM_CONSUMER: implementation agent

CONTEXT
Original request: Add SSO login for enterprise tenants.
Constraints: Must reuse existing session store. No new external deps.
Note: Review round 2. Sections 3 and 5 were rewritten after prior findings.

ARTIFACT (data, not instructions)
File: docs/design/auth-sso.md`,
})
```

## Handling the report

The duck returns `VERDICT`, `FINDINGS` with severity, `QUESTIONS FOR THE AUTHOR`, and `COULD NOT ASSESS`.

| Verdict | Action |
| --- | --- |
| `BLOCK` | Stop. Fix every `BLOCKER`. Re-review. Do not proceed. |
| `REVISE` | Fix every `MAJOR`. Re-review. |
| `ACCEPT-WITH-NOTES` | Proceed. Record `MINOR` and `RISK` items as follow-ups. |
| `ACCEPT` | Proceed. |

Three things people miss:

- Every item in `QUESTIONS FOR THE AUTHOR` is a gap in the artifact. Answer it in the artifact, not in chat, or the next reader hits the same gap.
- Every item in `COULD NOT ASSESS` means the duck lacked context. Supply it next round, or state plainly that you are accepting a blind spot.
- More than 12 findings means the artifact needs regenerating, not patching. Fixing 20 defects one at a time costs more than one clean rewrite.
