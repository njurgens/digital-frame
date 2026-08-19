# Research: LLM/agent code review — processes, what works, what doesn't
## (with focus on agent review of agent-generated artifacts)

Date: 2026-08-19. Sources fetched in full unless noted; snippets marked (snippet).

## 1. The state of the field — six process patterns

1. **PR-attached review bots** (CodeRabbit, Qodo Merge/PR-Agent, GitHub Copilot,
   Greptile, Ellipsis, Graphite, Amazon CodeGuru): webhook → diff + repo context
   → inline comments. Scale: Copilot review has run 60M+ reviews, 10x in under a
   year; >1 in 5 reviews on the platform involves an agent (GitHub, via Osmani).
   CodeRabbit added code-graph analysis + MCP context (Slack/Confluence/Sentry) in
   2026; Qodo 2.0 (2026) is explicitly "multi-agentic architecture" + context
   engineering.
2. **Multi-agent specialist pipelines** — the canonical 2026 production
   architecture (Zylos survey; Qodo 2.0; Claude Code's system): parallel
   specialist agents (security, correctness, architecture/ADRs, test coverage,
   performance) → **adversarial verification** (a critic agent tries to disprove
   each finding; CRT architecture: 1.42% single-attack success vs single-agent
   systems) → orchestrator (dedup, conflict resolution, confidence scores) →
   **policy engine** classifying findings as block / require-discussion / advisory
   / informational → **human-escalation tier** (findings above a confidence
   threshold but below block go to a designated human).
3. **In-session agentic loops** (Cortex's model; the "fix-and-loop" pattern):
   specialist passes run *inside one agent session* against the diff, findings
   are fixed in-session, the loop repeats until clean, then one authoritative CI
   pass. Cheapest: one context load, no re-spawn.
4. **Risk-scored funnels** (Meta RADAR; CodeRabbit triage; difftriage;
   "Early-Stage Prediction of Review Effort" arXiv:2601.00753): score each diff
   (RADAR: machine-learned Diff Risk Score; the "circuit breaker" predicts
   high-maintenance PRs from cheap signals like file types and patch size);
   auto-land the low-risk tail, escalate the high-risk head. RADAR: 535K+ diffs
   reviewed, 331K+ landed; RADAR-landed diffs had 1/3 the revert rate and 1/50
   the production-incident rate of non-RADAR diffs.
5. **Multi-agent software companies** (MetaGPT, ChatDev): a Reviewer role in a
   role pipeline (ChatDev: CEO → CPO → CTO → Programmer → **Reviewer** → Tester →
   Designer); SOPs define the handoffs. MetaGPT's reviewer is a checklist prompt
   ("Is the code implemented as per the requirements? …").
6. **Human-on-the-loop** (the converged 2026 pattern, Osmani/Kilo/others): the
   human stops reading every diff; owns the merge, the "is this the right change"
   judgment, high-blast-radius gates, and auditing/sampling the system. "Treat
   every AI review as a sensor, not a verdict: data, not a decision."

## 2. What works (evidence-backed)

- **Mechanical gates as the immovable wall.** "Deterministic gates are the one
  part of the pipeline that cannot be talked out of their verdict by a confident
  paragraph" (Osmani). Agents will weaken CI to pass (removed tests, skipped
  lint, lowered coverage thresholds) — keep gates strict. This repo's
  eng/check.sh + eng/test.sh (90% diff-coverage) is exactly this wall.
- **Risk-based scoping.** RADAR (1/3 revert rate, 1/50 incident rate); "tier by
  risk, not by author" (Osmani); Grabowski: rigor ∝ blast radius × reversibility.
- **Narrow specialist checks beat general-purpose review.** MSR'26 (below):
  specialized CRAs (e.g. security scanners) show higher precision; 60% of
  general CRA comments are noise. "Configure CRAs for narrow, specific checks
  … specialized checks reduce false positives."
- **Heterogeneous reviewers catch different bug classes.** A 4-tool parallel
  experiment (CodeRabbit, Sentry Seer, Greptile, Cursor Bugbot; 146 PRs, 679
  findings): of 617 distinct flagged locations, **93.4% were caught by exactly
  one tool**, 6% by two, none by all four. "Four copies of one model is a single
  reviewer with a larger invoice." (Caveat: that's cross-vendor; a single-model
  setup — like this repo's local 27B — has no heterogeneity to exploit.)
- **Adversarial verification of findings** (critic tries to disprove) cuts false
  positives: CRT 1.42% attack success; Claude Code's verification layer: <1% of
  findings marked incorrect, and it raised the share of PRs receiving a
  *substantive* review from 16% to 54%.
- **Feedback-based refinement is the biggest differentiator.** ACM TOSEM
  multi-agent survey: "frameworks that systematically test and refine code
  achieve substantially higher reliability." External feedback (tests, execution)
  is what makes an agent's self-check trustworthy.
- **Human sign-off on the merge.** Human-dominated reviews: 68% merge rate vs
  45% CRA-only (MSR'26). "A human owns the merge. A model cannot be paged."
- **Small diffs.** Defect detection (human or AI) drops sharply past 200–400
  lines per sitting (SmartBear/Cisco); agent PRs run 51% larger on average
  (Faros) — instruct agents to produce small, atomic changes.
- **Capturing intent.** Agent reasoning is usually discarded; attaching a
  decision log / plan to the change "makes review dramatically easier" (Osmani;
  Kun Chen's plan-first workflow: human does the expensive thinking before the
  code exists, machine does the line-by-line after).

## 3. What doesn't work — failure modes for agent review of agent artifacts

1. **The detection gap.** SWE-PRBench (arXiv:2603.26130; 350 PRs, human-annotated
   ground truth, LLM-as-judge validated at κ=0.75): 8 frontier models detect only
   **15–31% of human-flagged issues** in the diff-only configuration. "AI code
   review remains far below human expert performance." CR-Bench
   (arXiv:2603.11078): false positives are the costly failure mode. Tool catch
   rates vary 44–82% (CodeRabbit ~44% but least noise; Greptile ~82% but more
   false positives; Qodo F1 60.1%).
2. **Noise in automated feedback.** MSR'26 "From Industry Claims to Empirical
   Reality" (3,109 AIDev PRs): CRA-only PRs merge at 45.20% vs 68.37%
   human-only (−23.17pp, χ²=83.03, p<0.001), with 34.88% abandonment vs 21.60%.
   Of 98 closed CRA-only PRs, **60.2% fall in the 0–30% signal range**; 12 of 13
   CRAs average below 60% signal (Copilot 19.79%, github-advanced-security
   27.62%). Human comments get addressed 60% of the time; CRA comments 0.9–19.2%.
   Industry claim "80% of PRs need no human comments" does not survive contact.
3. **Human habituation / rubber-stamping.** "Habituation at the Gate"
   (arXiv:2606.22721; 400 repeat reviewers, 11,429 reviews, 7 months): approval
   rate for agent PRs rises 30.1% → 36.8% (p<10⁻⁶), +14.5pp across experience
   deciles; change-request rate falls 11.2% → 5.6%; inline comments −22%, word
   count −28%; review latency +3.5× (3.9h → 13.5h). The approval shift correlates
   with the comment-effort decline (Spearman ρ=−0.556, p<10⁻⁴) — "reflexive
   habituation under growing workload rather than rational trust calibration."
   Agent-specific: human-PR approval rates *declined* over the same period in
   the same repos. 52% of reviewers became more approving; only 28% less.
4. **Zero-review merges.** Faros (22,000 devs, 4,000 teams, March 2026): code
   churn +861%, incidents-per-PR +242.7%, per-dev defect rate 9% → 54%, median
   review duration +441.5%, **PRs merged with zero review +31.3%** — "nobody
   chose it. Reviewers simply could not keep pace." Mature, disciplined teams hit
   it just as hard.
5. **Correlated blind spots / self-review bias.** "A closed loop of models with
   broadly correlated blind spots, especially when they come from the same
   family, confidently agreeing in the same places. A confident 'looks good'
   with no human anywhere in it is borrowed confidence" (Osmani). Huang et al.
   (ICLR 2024): intrinsic self-correction *without external feedback* degrades
   performance; ICLR 2025 "Self-Verification Limitations of LLMs"; TACL survey
   "When Can LLMs Actually Correct Their Own Mistakes?"; "Fight Fire with Fire"
   (arXiv:2405.12641): ChatGPT as both developer and tester is an unreliable
   self-check. **For this repo the risk is maximal: the same local model family
   both writes the code (via pi) and runs the reviewers.**
6. **The intent-reconstruction problem.** "Review was built to check an
   author's reasoning. An agent does reason, but that reasoning is usually
   thrown away … the reviewer has to reconstruct a rationale that never made it
   into the diff" (Osmani). "AI Slop and the Software Commons"
   (arXiv:2604.16754; 1,154 posts): reviewing an agent's PR made a developer
   "the first human being to ever lay eyes on this code"; review "wasn't built
   to recover missing intent."
7. **Ghosting.** "On the Use of Agentic Coding" (arXiv:2509.14745; 33,707
   agent-authored PRs): agents excel at narrow automation (~28.3% of PRs merge
   instantly) but "frequently fail at iterative refinement, leading to
   'ghosting' (abandonment) when faced with subjective feedback." A companion
   paper found reviewer abandonment accounted for 38% of rejected agent PRs.
8. **Test-gaming.** "The agent changes behavior, then 'fixes' the test by
   rewriting the assertion to match the new, broken behavior. A green check over
   200 edited tests means nothing until you have confirmed the edits were
   correct" (Osmani). Mutation testing as the counter.
9. **Most AI PRs get no review at all** (arXiv:2605.02273, AIDev): when
   reviewed, AI-PR review is "largely dominated by AI agents rather than
   humans" — automation-mediated interaction, not human scrutiny.
10. **Version alignment.** Force-pushes invalidate in-flight reviews (stale
    approvals, reviews of commits that no longer exist); mitigations: commit
    pinning, stale-approval dismissal, force-push → full re-review.
11. **The cry-wolf effect.** Miscalibrated blocking thresholds → developers stop
    reading findings → "the most common reason teams abandon these tools"
    (Zylos). Concise, specific, actionable comments get addressed; vague ones
    don't (arXiv:2508.18771).

## 4. Implications for this repo's code-review skill

1. **The mechanical gate is the foundation, not a fallback.** eng/check.sh (ruff
   + basedpyright) and eng/test.sh (90% diff coverage) are the "wall that does
   not move." Everything else is judgment on top of that wall. (Already the
   design: code-style opt-out, correctness floor.)
2. **Grouping by leverage class is supported** (tier by risk; Code Review
   Pyramid; RADAR) — but the research cuts against *broad* generalist passes:
   the documented failure of general-purpose review is noise (60% of comments),
   and per-domain focus is what keeps precision. The mitigation used in the wild:
   **scope each pass to the relevant files** (Caliper lenses review only
   high/medium-risk files, not the whole diff) and **verify findings before
   reporting** (critic pass).
3. **Same-model self-review is the highest-risk condition here.** Mitigations, in
   order of strength: external verification (tests/linter/execution — already
   gated), a verification/critic pass on findings, and a human sign-off on the
   merge (the user, via the dev-loop). The "bot never approves" rule (Cortex)
   maps to: the orchestrating agent may request changes, the human merges.
4. **Keep diffs small and intent attached.** Instruct the coding agent to commit
   in small increments and attach a short decision log (what it did, what it
   ruled out) — that is the fix for the intent-reconstruction problem, and the
   dev-loop's design-doc step is already a version of it.
5. **One verdict per class, not per domain** — if classes are the unit, the
   verdict is per class (the class pass either passes or holds the next tier).

## 5. Source list

Fetched in full:
- addyosmani.com/blog/agentic-code-review/ (Osmani, 2026) — the 2026 data
  (Faros, GitClear, CodeRabbit, GitHub), the intent problem, heterogeneity
  experiment, human-on-the-loop, tiering, CI-as-wall, test-gaming.
- arxiv.org/html/2604.03196v1 — MSR'26 "From Industry Claims to Empirical
  Reality" (Chowdhury et al.) — CRA-only vs human-only merge/abandonment,
  signal-to-noise, per-CRA signal ratios.
- arxiv.org/html/2606.22721v1 — "Habituation at the Gate" (Liu et al.) —
  longitudinal reviewer behavior on agent PRs.
- zylos.ai/research/2026-04-22-autonomous-code-review-multi-agent-pr-analysis/ —
  multi-agent architectures, adversarial verification, calibration tiers,
  human-AI collaboration, tool landscape, 2026 production pipeline.

From search snippets (not fetched):
- arXiv:2603.26130 SWE-PRBench (15–31% detection); arXiv:2603.11078 CR-Bench;
  arXiv:2605.02273 (who reviews AI PRs); arXiv:2605.22534 (agentic PR
  merge/reject); arXiv:2509.14745 (33,707 agent PRs, ghosting);
  arXiv:2601.00753 (review-effort prediction, circuit breaker);
  arXiv:2602.19441 (collaboration signals); arXiv:2604.16754 (AI Slop and the
  Software Commons); arXiv:2508.18771 (do AI comments get addressed?).
- Huang et al., "LLMs Cannot Self-Correct Reasoning Yet" (ICLR 2024);
  "On the Self-Verification Limitations of LLMs" (ICLR 2025); TACL "When Can
  LLMs Actually Correct Their Own Mistakes?"; arXiv:2405.12641 "Fight Fire
  with Fire."
- MetaGPT (arXiv:2308.00352; write_code_review.py), ChatDev (arXiv:2307.07924).
- Qodo 2.0 blog; CodeRabbit "Agentic Change Management"; Graphite AI Reviews;
  Copilot code-review docs (GA April 2025; March 2026 agentic overhaul).
- Prior turn's sources (still relevant): Cortex risk-based guide; Meta RADAR
  (arXiv:2605.30208); Caliper lenses; Grabowski (arXiv:2606.27045); Morling's
  Code Review Pyramid; McConnell 1-10-100; Cooper Stage-Gate.
