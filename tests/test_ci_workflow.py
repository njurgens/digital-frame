"""Contract tests for the GitHub Actions CI workflow (``.github/workflows/ci.yml``).

Issue #58: the repo had no CI, so a PR breaking the build, the type check, or
the 90% diff-coverage gate could merge silently. The workflow is the merge
gate for ``main``: three jobs, each a thin wrapper around the existing
``eng/`` scripts (``sync.sh``, ``check.sh``, ``test.sh``), running on every
pull request and on pushes to ``main``.

These tests pin that contract so a later edit cannot silently weaken the
gate: the triggers, the exact job set, the Python/uv provisioning, the
script each job runs, the full-history checkout the coverage gate needs,
and SHA pinning of every external action.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: A 40-hex-digit git commit SHA — the form a pinned ``uses:`` reference takes.
_SHA = re.compile(r"^[0-9a-f]{40}$")

#: The ``eng/`` script each job must run, keyed by job id.
JOB_SCRIPTS = {
    "build": "eng/sync.sh",
    "check": "eng/check.sh",
    "test": "eng/test.sh",
}


@pytest.fixture(scope="module")
def workflow() -> dict:
    """The parsed workflow file (read-only, so module-scoped)."""
    assert WORKFLOW.is_file(), f"missing CI workflow: {WORKFLOW}"
    data = yaml.safe_load(WORKFLOW.read_text())
    assert isinstance(data, dict), "workflow must be a YAML mapping"
    return data


def _triggers(workflow: dict) -> dict:
    """The workflow's ``on:`` trigger mapping.

    YAML 1.1 (which PyYAML implements) parses the bare word ``on`` as the
    boolean ``True``, so the key may surface as either ``"on"`` or ``True``.
    """
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict), "workflow must declare an ``on:`` mapping"
    return triggers


def _steps(workflow: dict, job_id: str) -> list[dict]:
    """The step list of *job_id*, asserting the job exists and has steps."""
    job = workflow["jobs"].get(job_id)
    assert isinstance(job, dict), f"missing job: {job_id}"
    steps = job.get("steps")
    assert isinstance(steps, list) and steps, f"job {job_id} must have steps"
    return steps


def _step_by_action(steps: list[dict], action: str) -> dict | None:
    """The step whose ``uses`` references *action* (e.g. ``actions/checkout``).

    The part of ``uses`` before the ``@`` is the action's repo or local path,
    so this matches whether the reference is pinned to a SHA or a tag.
    """
    for step in steps:
        uses = step.get("uses")
        if isinstance(uses, str) and uses.split("@", 1)[0] == action:
            return step
    return None


def test_workflow_exists_and_parses(workflow: dict) -> None:
    """The workflow file exists and is a YAML mapping with jobs."""
    assert isinstance(workflow.get("jobs"), dict), "workflow must declare jobs"


def test_triggers_on_every_pull_request_and_pushes_to_main(workflow: dict) -> None:
    """The gate runs on every pull request and on pushes to main."""
    triggers = _triggers(workflow)
    # A bare ``pull_request:`` (null value) means every pull request event;
    # any filter (branches, types) would silently narrow the gate.
    assert triggers.get("pull_request") is None, (
        "pull_request trigger must be unrestricted (no branch/type filter)"
    )
    push = triggers.get("push")
    assert isinstance(push, dict), "workflow must run on pushes"
    assert push.get("branches") == ["main"], "push trigger must cover main"


def test_jobs_are_exactly_build_check_test(workflow: dict) -> None:
    """Exactly the three gate jobs exist — no extra, no missing."""
    assert set(workflow["jobs"]) == set(JOB_SCRIPTS)


@pytest.mark.parametrize("job_id", sorted(JOB_SCRIPTS))
def test_job_provisions_python_313_and_uv(workflow: dict, job_id: str) -> None:
    """Every job checks out and provisions Python 3.13 and uv."""
    steps = _steps(workflow, job_id)
    assert _step_by_action(steps, "actions/checkout") is not None, (
        f"{job_id}: no actions/checkout step"
    )
    setup_python = _step_by_action(steps, "actions/setup-python")
    assert setup_python is not None, f"{job_id}: no actions/setup-python step"
    with_ = setup_python.get("with") or {}
    assert with_.get("python-version") == "3.13", (
        f"{job_id}: setup-python must provision 3.13 (pyproject requires >=3.13)"
    )
    assert _step_by_action(steps, "astral-sh/setup-uv") is not None, (
        f"{job_id}: no astral-sh/setup-uv step"
    )


@pytest.mark.parametrize("job_id", sorted(JOB_SCRIPTS))
def test_job_runs_its_eng_script(workflow: dict, job_id: str) -> None:
    """Each job runs exactly its own eng/ script — the thin-wrapper contract."""
    runs = [step["run"] for step in _steps(workflow, job_id) if "run" in step]
    expected = f"bash {JOB_SCRIPTS[job_id]}"
    assert runs == [expected], f"{job_id} must run exactly one step: `{expected}`"


def test_test_job_checkout_makes_origin_main_resolvable(workflow: dict) -> None:
    """The coverage gate diffs against ``origin/main`` by default.

    ``actions/checkout``'s default (fetch-depth 1) fetches only the PR's
    merge commit on pull request events and never creates an ``origin/main``
    ref, so ``diff-cover` would fail with "unknown revision" on every PR.
    The test job's checkout must therefore fetch full history (or at least
    the main branch) for the gate to have a base to diff against.
    """
    checkout = _step_by_action(_steps(workflow, "test"), "actions/checkout")
    assert checkout is not None, "test job: no actions/checkout step"
    with_ = checkout.get("with") or {}
    full_history = with_.get("fetch-depth") == 0
    fetches_main = "main" in (with_.get("fetch") or [])
    assert full_history or fetches_main, (
        "test job checkout must make origin/main resolvable "
        "(fetch-depth: 0 or an explicit fetch of main)"
    )


def test_external_actions_are_sha_pinned(workflow: dict) -> None:
    """Every external action is pinned to a commit SHA, not a mutable tag.

    A tag like ``@v7`` moves when the action ships a new release, which would
    silently change what the merge gate runs; a SHA cannot.
    """
    for job_id, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if not isinstance(uses, str):
                continue
            assert not uses.startswith("./"), f"{job_id}: unexpected local action"
            _, sep, ref = uses.rpartition("@")
            assert sep and _SHA.match(ref), f"{job_id}: action not pinned to a SHA: {uses}"
