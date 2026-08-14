#!/usr/bin/env python3
"""Lint a Markdown design doc for the mechanical rules in the design-docs skill.

Catches what a script can catch: implementation content, missing sections, broken
Mermaid, dangling ID references, banned phrases, size and diagram limits. It cannot
judge whether an argument is sound -- that is the reviewer's job, and passing this
linter is not the same as passing review.

Usage:
    python lint_design_doc.py DOC.md
    python lint_design_doc.py DOC.md --json
    python lint_design_doc.py DOC.md --mini      # relax section + size rules
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict

SEVERITIES = ["blocking", "major", "minor", "nit"]

REQUIRED_SECTIONS = {
    "summary": r"\bsummary\b",
    "context": r"\bcontext\b",
    "goals": r"\bgoals?\b",
    "constraints/assumptions": r"\bconstraints?\b|\bassumptions?\b",
    "quality scenarios": r"\bquality\b",
    "solution strategy": r"\bsolution\b|\bstrategy\b",
    "architecture views": r"\barchitectur\w*\b|\bviews?\b|\bdesign\b",
    "decisions": r"\bdecisions?\b",
    "alternatives": r"\balternatives?\b",
    "cross-cutting": r"\bcross.?cutting\b|\bconcerns?\b",
    "risks": r"\brisks?\b|\btechnical debt\b",
    "validation": r"\bvalidation\b|\bhow we.?ll know\b|\bsuccess criteria\b",
    "open questions": r"\bopen questions?\b|\bunresolved\b",
}

BANNED_PHRASES = [
    "industry best practice", "best practices", "state of the art",
    "robust and scalable", "seamless", "leverage the", "as appropriate",
    "where necessary", "this document describes", "it should be noted",
    "cutting edge", "world-class", "battle-tested",
]

WEASEL_WORDS = ["simply", "just ", "obviously", "of course", "clearly,"]

QUALITY_WORDS = [
    "fast", "faster", "scalable", "scalability", "secure", "reliable",
    "reliability", "performant", "performance", "highly available",
    "low latency", "efficient", "robust",
]

# Implementation smells: (regex, label, severity)
IMPL_PATTERNS = [
    (r"^\s*(CREATE TABLE|ALTER TABLE|SELECT .+ FROM|INSERT INTO)\b", "SQL statement", "blocking"),
    (r"\b(npm install|pip install|yarn add|apt-get install|brew install)\b", "install command", "blocking"),
    (r"\b(kubectl|docker run|docker build|terraform apply|helm install)\b", "CLI invocation", "blocking"),
    (r"(^|\s)(src|lib|app|pkg|internal)/[\w./-]+\.(py|ts|tsx|js|jsx|go|java|rb|rs|cs|kt|php)\b", "source file path", "blocking"),
    (r"\b\w+\.(py|ts|tsx|jsx|go|java|rb|rs|kt|cs)\b", "source filename", "major"),
    (r"\b[A-Z]\w*(Impl|Repository|Controller|DTO|ServiceImpl|Factory|Manager)\b", "code-level class name", "major"),
    (r"^\s*(GET|POST|PUT|PATCH|DELETE)\s+/\S+", "endpoint listing", "major"),
    (r"^\s*(Phase|Step|Sprint|Week)\s*\d+\s*[:.-]\s*(create|add|implement|build|write|refactor|deploy)\b", "engineering task list", "blocking"),
    (r"^\s*(def |class |function |func |public |private |const |let |var |import |from \w+ import)\b", "code statement", "blocking"),
    (r"@(Autowired|Component|Injectable|Entity|Table|Override|RestController)\b", "framework annotation", "blocking"),
]

MERMAID_RESERVED = {"end", "graph", "class", "state", "subgraph", "o", "x", "style", "click"}

MERMAID_TYPES = [
    "flowchart", "graph", "sequenceDiagram", "classDiagram", "stateDiagram-v2",
    "stateDiagram", "erDiagram", "journey", "gantt", "pie", "timeline", "mindmap",
    "gitGraph", "quadrantChart", "requirementDiagram", "C4Context", "C4Container",
    "C4Component", "C4Dynamic", "C4Deployment", "block-beta", "architecture-beta",
    "packet-beta", "sankey-beta", "xychart-beta", "radar-beta", "kanban", "treemap",
]

DIAGRAM_LIMITS = {
    "sequence_participants": 8,
    "sequence_messages": 25,
    "state_states": 10,
    "class_classes": 12,
    "er_entities": 12,
    "flowchart_nodes": 20,
    "diagram_lines": 40,
}

ID_PREFIXES = ["G", "NG", "C", "A", "QA", "D", "ALT", "F", "R", "TD", "V", "OQ"]
ID_RE = re.compile(r"\b(" + "|".join(ID_PREFIXES) + r")-(\d+)\b")

PROVENANCE_RE = re.compile(r"\[(verified|reported|assumed|unknown)\b", re.I)


@dataclass
class Finding:
    severity: str
    location: str
    rule: str
    detail: str

    def key(self):
        return (SEVERITIES.index(self.severity), self.location)


class Doc:
    def __init__(self, text: str):
        self.text = text
        self.lines = text.split("\n")
        self.front_matter, self.body_start = self._split_front_matter()
        self.fences = self._find_fences()
        self.prose_lines = self._prose_lines()

    def _split_front_matter(self):
        if self.lines and self.lines[0].strip() == "---":
            for i in range(1, min(len(self.lines), 60)):
                if self.lines[i].strip() == "---":
                    return "\n".join(self.lines[1:i]), i + 1
        return None, 0

    def _find_fences(self):
        """Return list of (start_line, end_line, lang, content_lines). 1-indexed lines."""
        fences, open_fence = [], None
        for i, line in enumerate(self.lines, start=1):
            m = re.match(r"^\s*(`{3,}|~{3,})\s*(\S*)", line)
            if not m:
                continue
            marker, lang = m.group(1), m.group(2)
            if open_fence is None:
                open_fence = (i, marker[0] * len(marker), lang)
            elif line.strip().startswith(open_fence[1][0] * 3):
                start, _, flang = open_fence
                fences.append((start, i, flang, self.lines[start:i - 1]))
                open_fence = None
        if open_fence is not None:
            fences.append((open_fence[0], len(self.lines), open_fence[2], self.lines[open_fence[0]:]))
        return fences

    def _prose_lines(self):
        """Line numbers (1-indexed) that are outside any fence."""
        inside = set()
        for start, end, _, _ in self.fences:
            inside.update(range(start, end + 1))
        return [(i, l) for i, l in enumerate(self.lines, start=1) if i not in inside]

    def word_count(self):
        return len(" ".join(l for _, l in self.prose_lines).split())

    def headings(self):
        return [(i, l.strip("# ").strip()) for i, l in self.prose_lines if l.lstrip().startswith("#")]

    def mermaid_blocks(self):
        return [(s, e, c) for s, e, lang, c in self.fences if lang.lower() == "mermaid"]

    def nonmermaid_fences(self):
        return [(s, e, lang, c) for s, e, lang, c in self.fences if lang.lower() != "mermaid"]


def check_front_matter(doc, F):
    if doc.front_matter is None:
        F.append(Finding("major", "top", "front-matter",
                         "No YAML front matter. Reviewers and downstream agents key off status, "
                         "dates, and supersedes."))
        return
    required = ["title", "status", "created"]
    missing = [k for k in required if not re.search(rf"^{k}\s*:", doc.front_matter, re.M)]
    if missing:
        F.append(Finding("minor", "front matter", "front-matter",
                         f"Missing key(s): {', '.join(missing)}."))


def check_sections(doc, F, mini):
    if mini:
        return
    heads = " \n ".join(h.lower() for _, h in doc.headings())
    for name, pattern in REQUIRED_SECTIONS.items():
        if not re.search(pattern, heads, re.I):
            sev = "major" if name in ("validation", "open questions", "quality scenarios") else "blocking"
            F.append(Finding(sev, "structure", "missing-section",
                             f"No section matching '{name}'."))


def check_impl_content(doc, F):
    for start, end, lang, content in doc.nonmermaid_fences():
        label = lang or "unlabeled"
        if label.lower() in ("yaml", "yml") and start <= (doc.body_start + 2):
            continue
        F.append(Finding("blocking", f"line {start}", "code-fence",
                         f"Fenced `{label}` block ({end - start - 1} lines). Only ```mermaid "
                         f"belongs in a design doc -- move this up the abstraction ladder or link it."))

    for lineno, line in doc.prose_lines:
        if line.lstrip().startswith(("|", ">")):
            continue
        for pattern, label, sev in IMPL_PATTERNS:
            if re.search(pattern, line):
                F.append(Finding(sev, f"line {lineno}", "implementation-content",
                                 f"{label}: {line.strip()[:80]}"))
                break


def check_phrases(doc, F):
    for lineno, line in doc.prose_lines:
        low = line.lower()
        for phrase in BANNED_PHRASES:
            if phrase in low:
                F.append(Finding("minor", f"line {lineno}", "banned-phrase",
                                 f"'{phrase}' -- states nothing a reader can contest."))
        for w in WEASEL_WORDS:
            if w in low:
                F.append(Finding("nit", f"line {lineno}", "weasel-word",
                                 f"'{w.strip()}' usually sits on top of the contested part."))


def check_quality_words(doc, F):
    has_qa = bool(re.search(r"\bQA-\d+", doc.text))
    if has_qa:
        return
    hits = set()
    for _, line in doc.prose_lines:
        low = line.lower()
        for w in QUALITY_WORDS:
            if re.search(rf"\b{re.escape(w)}\b", low):
                hits.add(w)
    if hits:
        F.append(Finding("major", "whole doc", "unquantified-quality",
                         f"Quality words used ({', '.join(sorted(hits)[:6])}) but no QA-n "
                         f"scenarios defined to make them measurable."))


def check_ids(doc, F):
    defined, referenced = {}, {}
    for lineno, line in doc.prose_lines:
        stripped = line.strip()
        is_def = (
            re.match(r"^[-*]\s*\*\*(" + "|".join(ID_PREFIXES) + r")-\d+\*\*", stripped)
            or re.match(r"^\|\s*\*?\*?(" + "|".join(ID_PREFIXES) + r")-\d+", stripped)
            or re.match(r"^#{1,6}\s*(" + "|".join(ID_PREFIXES) + r")-\d+", stripped)
        )
        for m in ID_RE.finditer(line):
            ident = f"{m.group(1)}-{m.group(2)}"
            if is_def and m.start() < 12:
                defined.setdefault(ident, lineno)
            else:
                referenced.setdefault(ident, lineno)
    dangling = {k: v for k, v in referenced.items() if k not in defined}
    for ident, lineno in sorted(dangling.items(), key=lambda kv: kv[1])[:10]:
        F.append(Finding("minor", f"line {lineno}", "dangling-id",
                         f"{ident} is referenced but never defined in a bullet, table row, or heading."))
    if not defined:
        F.append(Finding("major", "whole doc", "no-ids",
                         "No stable IDs (G-n, QA-n, D-n, ...). IDs let reviewers and implementing "
                         "agents reference specific claims."))
    orphan_goals = [g for g in defined if g.startswith("G-") and g not in referenced]
    for g in sorted(orphan_goals):
        F.append(Finding("major", "structure", "orphan-goal",
                         f"{g} is defined but never referenced again -- no decision or view visibly serves it."))


def check_provenance(doc, F):
    markers = len(PROVENANCE_RE.findall(doc.text))
    numeric = 0
    for lineno, line in doc.prose_lines:
        if re.search(r"\b\d+(\.\d+)?\s*(ms|s|m|h|k|K|M|GB|MB|TB|%|rps|qps|/s|req/s)\b", line):
            numeric += 1
    if numeric >= 3 and markers == 0:
        F.append(Finding("major", "whole doc", "no-provenance",
                         f"{numeric} lines carry quantities but the doc has no provenance markers "
                         f"([verified: ...] / [reported: ...] / [assumed] / [unknown]). Unsourced "
                         f"numbers read as authoritative and get designed against."))


def check_open_questions(doc, F):
    m = re.search(r"^#{1,6}.*open questions?.*$", doc.text, re.I | re.M)
    if not m:
        return
    tail = doc.text[m.end():]
    nxt = re.search(r"^#{1,6}\s", tail, re.M)
    section = tail[: nxt.start()] if nxt else tail
    content = [l for l in section.split("\n")
               if l.strip() and not re.match(r"^\s*\|[\s\-:|]+\|\s*$", l)]
    substantive = [l for l in content if len(l.strip()) > 12]
    if len(substantive) <= 1:
        F.append(Finding("major", "open questions", "empty-open-questions",
                         "Open questions section is effectively empty. A draft with no unknowns is "
                         "either trivial or hiding them -- or say explicitly why the space is closed."))


def check_bullet_ratio(doc, F):
    body = [l for _, l in doc.prose_lines if l.strip() and not l.lstrip().startswith("#")]
    if len(body) < 40:
        return
    bullets = sum(1 for l in body if re.match(r"^\s*([-*+]|\d+\.)\s", l))
    tables = sum(1 for l in body if l.lstrip().startswith("|"))
    ratio = (bullets + tables) / len(body)
    if ratio > 0.65:
        F.append(Finding("major", "whole doc", "bullet-mush",
                         f"{ratio:.0%} of body lines are bullets or table rows. Reasoning belongs in "
                         f"prose; a doc this fragmented has no argument in it."))


def check_size(doc, F, mini):
    wc = doc.word_count()
    ceiling = 1500 if mini else 8000
    if wc > ceiling:
        F.append(Finding("major", "whole doc", "over-length",
                         f"{wc} words, past the {ceiling}-word ceiling. Split into a parent doc plus children."))
    if wc < 200:
        F.append(Finding("minor", "whole doc", "thin",
                         f"Only {wc} words -- likely missing the argument."))
    return wc


def check_mermaid(doc, F, wc):
    blocks = doc.mermaid_blocks()
    if not blocks:
        F.append(Finding("blocking", "whole doc", "no-diagrams",
                         "No Mermaid diagrams. Architectural views are how a design doc carries "
                         "structure without descending into code."))
        return
    if wc > 800:
        expected_max = max(7, wc // 500)
        if len(blocks) > expected_max:
            F.append(Finding("minor", "whole doc", "diagram-sprawl",
                             f"{len(blocks)} diagrams for {wc} words. Roughly one per 500 words is "
                             f"the point where readers stop looking at any of them."))
    if len(blocks) > 7:
        F.append(Finding("minor", "whole doc", "diagram-count",
                         f"{len(blocks)} diagrams; 3-7 is the working range for a standard doc."))

    has_failure_path = False

    for start, end, content in blocks:
        loc = f"mermaid at line {start}"
        body = [l for l in content if l.strip()]
        if not body:
            F.append(Finding("blocking", loc, "empty-diagram", "Empty mermaid block."))
            continue

        first = body[0].strip()
        dtype = next((t for t in MERMAID_TYPES if first.startswith(t)), None)
        if dtype is None:
            F.append(Finding("blocking", loc, "mermaid-type",
                             f"First line '{first[:40]}' is not a recognized diagram type keyword."))
            continue
        if dtype == "graph":
            F.append(Finding("minor", loc, "legacy-syntax", "Use `flowchart` rather than legacy `graph`."))
        if dtype == "stateDiagram":
            F.append(Finding("minor", loc, "legacy-syntax",
                             "Use `stateDiagram-v2`; the v1 renderer is less capable."))
        if dtype.endswith("-beta") or dtype.startswith("C4"):
            F.append(Finding("nit", loc, "fragile-type",
                             f"`{dtype}` has uneven renderer support -- do not let a required claim "
                             f"depend on it rendering."))

        if len(body) > DIAGRAM_LIMITS["diagram_lines"]:
            F.append(Finding("minor", loc, "diagram-too-large",
                             f"{len(body)} source lines (limit {DIAGRAM_LIMITS['diagram_lines']}). Split the view."))

        _check_reserved_ids(body, dtype, loc, F)
        _check_diagram_size(body, dtype, loc, F)
        _check_edge_labels(body, dtype, loc, F)
        _check_code_in_labels(body, loc, F)

        joined = "\n".join(body)
        if dtype == "sequenceDiagram":
            if re.search(r"\b(alt|else|opt|critical|break)\b", joined) or "--x" in joined:
                has_failure_path = True
            participants = re.findall(r"^\s*participant\s+(\w+)", joined, re.M)
            if not participants:
                F.append(Finding("minor", loc, "implicit-participants",
                                 "Declare participants explicitly at the top so draw order is controlled."))

        _check_caption(doc, end, loc, F)
        _check_surrounding_prose(doc, start, end, loc, F)

    seq_blocks = [b for b in blocks if b[2] and any(
        l.strip().startswith("sequenceDiagram") for l in b[2] if l.strip())]
    if seq_blocks and not has_failure_path:
        F.append(Finding("major", "runtime views", "happy-path-only",
                         "No runtime view shows a failure path (no alt/else/opt fragment or --x "
                         "message). Designs that only diagram success are usually underthought."))


def _check_reserved_ids(body, dtype, loc, F):
    if dtype not in ("flowchart", "graph"):
        return
    for line in body:
        for m in re.finditer(r"(?:^|\s|-->|---)\s*([A-Za-z_]\w*)\s*(?:\[|\(|\{|-->)", line):
            ident = m.group(1)
            if ident.lower() in MERMAID_RESERVED and ident not in ("subgraph", "style", "click"):
                F.append(Finding("blocking", loc, "reserved-node-id",
                                 f"Node id '{ident}' is a Mermaid reserved word -- the diagram will "
                                 f"fail to render or render wrongly."))
                return


def _check_diagram_size(body, dtype, loc, F):
    joined = "\n".join(body)
    if dtype == "sequenceDiagram":
        names = set(re.findall(r"^\s*(?:participant|actor)\s+(\w+)", joined, re.M))
        if not names:
            names = set(re.findall(r"^\s*(\w+)\s*-[->x]", joined, re.M))
        msgs = len(re.findall(r"-[->x]{1,2}[>x]?", joined))
        if len(names) > DIAGRAM_LIMITS["sequence_participants"]:
            F.append(Finding("minor", loc, "over-limit",
                             f"{len(names)} participants (limit {DIAGRAM_LIMITS['sequence_participants']})."))
        if msgs > DIAGRAM_LIMITS["sequence_messages"]:
            F.append(Finding("minor", loc, "over-limit",
                             f"~{msgs} messages (limit {DIAGRAM_LIMITS['sequence_messages']})."))
    elif dtype.startswith("stateDiagram"):
        states = set(re.findall(r"(\w+)\s*-->", joined)) | set(re.findall(r"-->\s*(\w+)", joined))
        states.discard("")
        if len(states) > DIAGRAM_LIMITS["state_states"]:
            F.append(Finding("minor", loc, "over-limit",
                             f"{len(states)} states (limit {DIAGRAM_LIMITS['state_states']})."))
        if "[*]" not in joined:
            F.append(Finding("minor", loc, "no-initial-state",
                             "No `[*]` marker -- initial and terminal states are unmarked."))
    elif dtype == "classDiagram":
        classes = set(re.findall(r"^\s*class\s+(\w+)", joined, re.M))
        if len(classes) > DIAGRAM_LIMITS["class_classes"]:
            F.append(Finding("minor", loc, "over-limit",
                             f"{len(classes)} classes (limit {DIAGRAM_LIMITS['class_classes']})."))
        rels = re.findall(r'^\s*\w+\s+(?:"[^"]*"\s+)?(\*--|o--|<\|--|-->|\.\.>)', joined, re.M)
        quoted = len(re.findall(r'\w+\s+"[^"]+"\s*(?:\*--|o--|<\|--|-->|\.\.>)', joined))
        if rels and quoted == 0:
            F.append(Finding("minor", loc, "no-multiplicity",
                             "Class relationships carry no multiplicity annotations."))
        for bad in re.findall(r"^\s*[+\-#]?\s*(get\w+|set\w+)\s*\(", joined, re.M):
            F.append(Finding("major", loc, "code-preview-class",
                             f"Accessor '{bad}' -- this diagram is previewing code, not modelling the domain."))
            break
    elif dtype == "erDiagram":
        ents = set(re.findall(r"^\s*(\w+)\s*[|}o][|}o]?--", joined, re.M))
        ents |= set(re.findall(r"--[o|{][|{]?\s*(\w+)", joined))
        if len(ents) > DIAGRAM_LIMITS["er_entities"]:
            F.append(Finding("minor", loc, "over-limit",
                             f"{len(ents)} entities (limit {DIAGRAM_LIMITS['er_entities']})."))
    elif dtype in ("flowchart", "graph"):
        nodes = set(re.findall(r"([A-Za-z_]\w*)\s*[\[\(\{]", joined))
        if len(nodes) > DIAGRAM_LIMITS["flowchart_nodes"]:
            F.append(Finding("minor", loc, "over-limit",
                             f"{len(nodes)} nodes (limit {DIAGRAM_LIMITS['flowchart_nodes']})."))


def _check_edge_labels(body, dtype, loc, F):
    if dtype not in ("flowchart", "graph"):
        return
    edges = [l for l in body if re.search(r"--[->]|==>|-\.->", l)]
    if not edges:
        return
    labelled = sum(1 for l in edges if "|" in l)
    if labelled / len(edges) < 0.5:
        F.append(Finding("minor", loc, "unlabeled-edges",
                         f"{len(edges) - labelled} of {len(edges)} edges carry no label. An unlabeled "
                         f"arrow asserts a dependency without saying what flows."))


def _check_code_in_labels(body, loc, F):
    joined = "\n".join(body)
    for pattern, label in [
        (r"\b\w+\.(py|ts|tsx|js|go|java|rb|rs)\b", "source filename"),
        (r"\b[A-Z]\w*(Impl|Repository|Controller|DTO)\b", "code-level class name"),
        (r"\b(SELECT|INSERT INTO|CREATE TABLE)\b", "SQL"),
    ]:
        m = re.search(pattern, joined)
        if m:
            F.append(Finding("major", loc, "artifact-named-node",
                             f"{label} '{m.group(0)}' in a diagram label. Name responsibilities, "
                             f"not artifacts that do not exist yet."))
            return


def _check_caption(doc, end_line, loc, F):
    window = doc.lines[end_line: end_line + 4]
    if not any(re.search(r"figure\s*\d+", l, re.I) for l in window):
        F.append(Finding("minor", loc, "no-caption",
                         "No 'Figure N — <claim>' caption within 3 lines. The caption is where the "
                         "diagram states what it asserts."))


def _check_surrounding_prose(doc, start_line, end_line, loc, F):
    before = [l for l in doc.lines[max(0, start_line - 6): start_line - 1]
              if l.strip() and not l.lstrip().startswith(("#", "|", "```"))]
    after = [l for l in doc.lines[end_line: end_line + 8]
             if l.strip() and not l.lstrip().startswith(("#", "|", "```"))
             and not re.match(r"^\s*\*?figure", l, re.I)]
    if not before:
        F.append(Finding("minor", loc, "no-lead-prose",
                         "No prose immediately before the diagram stating the claim it makes."))
    if not after:
        F.append(Finding("minor", loc, "no-follow-prose",
                         "No prose after the diagram. A reader who cannot see the picture still "
                         "needs the design -- a diagram must not be the sole carrier of a claim."))


def check_alternatives(doc, F):
    m = re.search(r"^#{1,6}.*alternatives?.*$", doc.text, re.I | re.M)
    if not m:
        return
    tail = doc.text[m.end():]
    nxt = re.search(r"^#{1,2}\s", tail, re.M)
    section = tail[: nxt.start()] if nxt else tail
    words = len(section.split())
    alts = len(re.findall(r"\bALT-\d+", section)) or len(re.findall(r"^#{3,6}\s", section, re.M))
    if alts < 2:
        F.append(Finding("blocking", "alternatives", "too-few-alternatives",
                         f"Only {alts} alternative(s) found. A design with one option was not a design decision."))
    if not re.search(r"\b(better|advantage|wins?|stronger|superior|outperform)\b", section, re.I):
        F.append(Finding("blocking", "alternatives", "strawman-alternatives",
                         "No alternative is credited with doing anything better than the chosen design. "
                         "Every real alternative wins on something; if none does, these are strawmen."))
    if alts and words / max(alts, 1) < 40:
        F.append(Finding("major", "alternatives", "thin-alternatives",
                         f"~{words // max(alts, 1)} words per alternative -- too thin to have been "
                         f"seriously considered."))


def check_tradeoffs(doc, F):
    signals = re.findall(
        r"\b(trade.?off|we accept|accepting|at the cost of|in exchange for|we give up|"
        r"downside|drawback|the price is|we sacrifice)\b", doc.text, re.I)
    if len(signals) < 2:
        F.append(Finding("blocking", "whole doc", "no-tradeoffs",
                         f"Only {len(signals)} trade-off signal(s) in the whole document. A design doc "
                         f"that never says what it gives up is an implementation manual."))


def check_nongoals(doc, F):
    m = re.search(r"^#{1,6}.*non.?goals?.*$", doc.text, re.I | re.M)
    if not m:
        F.append(Finding("major", "goals", "no-nongoals",
                         "No non-goals section. Non-goals are what stop the same scope debate recurring."))
        return
    tail = doc.text[m.end():]
    nxt = re.search(r"^#{1,3}\s", tail, re.M)
    section = tail[: nxt.start()] if nxt else tail
    for line in section.split("\n"):
        if re.search(r"\b(should not|must not|will not|shouldn't|won't|no\s+\w+\s+loss|not crash|avoid)\b",
                     line, re.I) and len(line.strip()) > 10:
            F.append(Finding("major", "non-goals", "negated-goal",
                             f"'{line.strip()[:70]}' reads as a negated goal, not a non-goal. A non-goal "
                             f"is something that could reasonably have been a goal and was excluded."))
            break


def lint(text: str, mini: bool = False):
    doc = Doc(text)
    F: list[Finding] = []
    check_front_matter(doc, F)
    check_sections(doc, F, mini)
    check_impl_content(doc, F)
    check_phrases(doc, F)
    check_quality_words(doc, F)
    check_ids(doc, F)
    check_provenance(doc, F)
    check_open_questions(doc, F)
    check_bullet_ratio(doc, F)
    wc = check_size(doc, F, mini)
    check_mermaid(doc, F, wc)
    check_alternatives(doc, F)
    check_tradeoffs(doc, F)
    check_nongoals(doc, F)
    F.sort(key=lambda f: f.key())
    return doc, F


def verdict(findings):
    counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
    if counts["blocking"]:
        return "revise", counts
    if counts["major"]:
        return "revise", counts
    if counts["minor"]:
        return "accept-with-minors", counts
    return "accept", counts


def main():
    ap = argparse.ArgumentParser(description="Lint a Markdown design doc.")
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--mini", action="store_true", help="relax section and size rules for a mini doc")
    args = ap.parse_args()

    try:
        text = open(args.path, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    doc, findings = lint(text, mini=args.mini)
    v, counts = verdict(findings)

    if args.json:
        print(json.dumps({
            "path": args.path,
            "word_count": doc.word_count(),
            "diagrams": len(doc.mermaid_blocks()),
            "verdict": v,
            "counts": counts,
            "findings": [asdict(f) for f in findings],
        }, indent=2))
        return 0 if v.startswith("accept") else 1

    print(f"\n  {args.path}")
    print(f"  {doc.word_count()} words · {len(doc.mermaid_blocks())} diagrams\n")
    if not findings:
        print("  No mechanical findings. The argument still needs a human or reviewer pass.\n")
    else:
        width = max(len(f.location) for f in findings)
        current = None
        for f in findings:
            if f.severity != current:
                current = f.severity
                print(f"  {current.upper()}")
            print(f"    {f.location:<{width}}  [{f.rule}] {f.detail}")
        print()
    print("  " + " · ".join(f"{counts[s]} {s}" for s in SEVERITIES))
    print(f"  verdict: {v}")
    print("\n  The linter checks mechanics only. Whether the argument is sound, the "
          "alternatives\n  are real, and the design is right still needs the review rubric.\n")
    return 0 if v.startswith("accept") else 1


if __name__ == "__main__":
    sys.exit(main())
