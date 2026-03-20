"""Tests for ForgeProof data models."""

import re

from forgeproof.models import (
    CommandResult,
    EvalScorecard,
    FileChange,
    PhaseResult,
    PhaseStatus,
    Plan,
    PlanStep,
    Requirement,
    RunState,
    _run_id,
    _utcnow,
)


def test_utcnow_format():
    ts = _utcnow()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts)


def test_run_id_format():
    rid = _run_id()
    assert re.match(r"^fp_\d{8}_\d{6}_[0-9a-f]{8}$", rid)


def test_run_id_unique():
    assert _run_id() != _run_id()


def test_run_state_defaults():
    state = RunState()
    assert state.run_id.startswith("fp_")
    assert state.created_utc.endswith("Z")
    assert state.phases == []
    assert state.file_changes == []
    assert state.plan is None
    assert state.evaluation is None
    assert state.pack_path == ""
    assert state.trigger.type == "mention"
    assert state.issue.issue_iid == 0
    assert state.git.base_branch == "main"


def test_run_state_unique_ids():
    s1 = RunState()
    s2 = RunState()
    assert s1.run_id != s2.run_id


def test_file_change_default_action():
    fc = FileChange(path="src/main.py", content="print('hi')")
    assert fc.action == "create"


def test_file_change_explicit_action():
    fc = FileChange(path="x.py", content="x", action="modify")
    assert fc.action == "modify"


def test_phase_status_values():
    assert PhaseStatus.PASSED.value == "passed"
    assert PhaseStatus.FAILED.value == "failed"
    assert PhaseStatus.PENDING.value == "pending"
    assert PhaseStatus.SKIPPED.value == "skipped"


def test_phase_result_serialization():
    pr = PhaseResult(phase="test", status=PhaseStatus.PASSED, summary="ok")
    d = pr.model_dump()
    assert d["phase"] == "test"
    assert d["status"] == "passed"
    restored = PhaseResult.model_validate(d)
    assert restored.phase == "test"


def test_run_state_round_trip():
    state = RunState()
    state.file_changes.append(FileChange(path="a.py", content="x"))
    d = state.model_dump()
    restored = RunState.model_validate(d)
    assert restored.run_id == state.run_id
    assert len(restored.file_changes) == 1


def test_eval_scorecard_defaults():
    sc = EvalScorecard()
    assert sc.deterministic_pass is False
    assert sc.review_ready is False
    assert sc.requirements_coverage == 0.0
    assert sc.gate_failures == []


def test_plan_with_requirements():
    plan = Plan(
        requirements=[Requirement(id="REQ-1", description="Do X")],
        steps=[PlanStep(step=1, action="create", file_path="a.py", description="Create a")],
    )
    assert len(plan.requirements) == 1
    assert plan.requirements[0].source == "issue"
    assert plan.steps[0].file_path == "a.py"


def test_command_result_defaults():
    cr = CommandResult(name="test", command="pytest", exit_code=0)
    assert cr.stdout == ""
    assert cr.stderr == ""
    assert cr.duration_ms == 0
    assert cr.required is True
