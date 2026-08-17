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

### 1. Review one artifact

The default. Use it when you cannot proceed until the review is back.

```js
Agent({
  subagent_type: "rubber-duck",
  description: "Review auth design spec",
  run_in_background: true,
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

Each call returns an `agent_id`. Collect results:

```js
get_subagent_result({ agent_id: "<id from spawn>", wait: true })
```

Add `verbose: true` to see the duck's full reasoning instead of just the report:

```js
get_subagent_result({ agent_id: "<id>", wait: true, verbose: true })
```

### 2. Resume agents with 0 tool calls

The agent may fail with the following:
- Makes 0 tool calls because some fresh agents do not understand how to use tools. This is a bug in the agent, not your prompt. Resuming usually fixes it.
- error: run hit the output token limit before producing any text

You must nudge the agent to resume by running the `Agent` tool call with `resume` set to the `agent_id` of the previous run. The duck will pick up where it left off.

```js
  Agent(
      subagent_type="rubber-duck",
      description="Resume ducky review 5e9266bd",
      prompt="Resume your review of the the artifact file. Read it first, then produce the structured review with VERDICT, FINDINGS, QUESTIONS FOR THE AUTHOR, and COULD NOT
 ASESS.",
      resume="5e9266bd-42c0-41f",
  )
```

NEVER resort to performing the review yourself.  If after multiple attempts, the duck cannot complete the review, escalate to the user.

NEVER give up assuming it's an environment issue. 100% of the time its because the rubber-duck agent is not making tool calls correctly.

### 3. Re-review after fixes

Each review round must be a new spawn, not `resume`. Say which round it is and what changed, so the duck spends its turns on the changed parts.

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
