---
description: Draft, peer-review, and file a GitHub issue from the current conversation
argument-hint: "[what the issue is about]"
---
Create a GitHub issue for: ${@:-the topic we just discussed}

Load the `github-issues` skill (`.agents/skills/github-issues/SKILL.md`) and
follow it end to end:

1. Draft the issue in `.pi/tmp/issue-<slug>.md` using the skill's template and
   content guidance.
2. Get it reviewed: load the `code-review` and run skill's reviewer mechanism
   against the technical-communication domain only, with medium thinking.
3. Revise the draft per the review (max 2 rounds), then file it with the
   skill's `scripts/create-issue.sh`.

Report the issue URL when done.
