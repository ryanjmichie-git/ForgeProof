"""Tests for run manifest building."""

import hashlib
import json

from forgeproof.models import (
    EvalScorecard,
    IssueInfo,
    PhaseResult,
    PhaseStatus,
    RunState,
)
from forgeproof.provenance.run_manifest import (
    _sha256_file,
    build_run_manifest,
    write_run_manifest,
)


def _make_staging(tmp_path):
    """Create a minimal staging directory for testing."""
    # inputs
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    (inputs / "issue.json").write_text('{"title": "test"}', encoding="utf-8")

    # SOURCE
    source = tmp_path / "SOURCE"
    source.mkdir()
    (source / "main.py").write_text("print('hi')", encoding="utf-8")

    # FORGEPROOF
    fp = tmp_path / "FORGEPROOF"
    fp.mkdir()
    (fp / "decision_log.jsonl").write_text('{"entry": 1}\n{"entry": 2}\n', encoding="utf-8")

    return tmp_path


def _make_state():
    state = RunState()
    state.issue = IssueInfo(project_id=1, issue_iid=2, issue_title="Test")
    state.phases.append(PhaseResult(phase="test", status=PhaseStatus.PASSED, summary="ok"))
    state.evaluation = EvalScorecard(
        deterministic_pass=True,
        requirements_coverage=100.0,
        review_ready=True,
    )
    return state


# -- _sha256_file --

def test_sha256_file(tmp_path):
    f = tmp_path / "test.txt"
    content = b"hello world"
    f.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert _sha256_file(f) == expected


def test_sha256_file_empty(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_bytes(b"")
    expected = hashlib.sha256(b"").hexdigest()
    assert _sha256_file(f) == expected


# -- build_run_manifest --

def test_build_run_manifest_keys(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    manifest = build_run_manifest(state, staging)

    assert manifest["schema_version"] == "forgeproof-0.1"
    assert manifest["run_id"] == state.run_id
    assert "trigger" in manifest
    assert "source" in manifest
    assert "git" in manifest
    assert "phases" in manifest
    assert "inputs" in manifest
    assert "outputs" in manifest
    assert "audit" in manifest


def test_build_run_manifest_source(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    manifest = build_run_manifest(state, staging)

    assert manifest["source"]["project_id"] == 1
    assert manifest["source"]["issue_iid"] == 2
    assert manifest["source"]["issue_title"] == "Test"


def test_build_run_manifest_evaluation(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    manifest = build_run_manifest(state, staging)

    assert "evaluation" in manifest
    assert manifest["evaluation"]["review_ready"] is True


def test_build_run_manifest_no_evaluation(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    state.evaluation = None
    manifest = build_run_manifest(state, staging)

    assert "evaluation" not in manifest


def test_build_run_manifest_audit(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    manifest = build_run_manifest(state, staging)

    assert manifest["audit"]["entry_count"] == 2


def test_build_run_manifest_inputs(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    manifest = build_run_manifest(state, staging)

    assert len(manifest["inputs"]) >= 1
    assert manifest["inputs"][0]["type"] == "issue"


def test_build_run_manifest_outputs(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    manifest = build_run_manifest(state, staging)

    assert len(manifest["outputs"]) >= 1
    assert any("main.py" in o["path"] for o in manifest["outputs"])


# -- write_run_manifest --

def test_write_run_manifest(tmp_path):
    staging = _make_staging(tmp_path)
    state = _make_state()
    path = write_run_manifest(state, staging)

    assert path.exists()
    assert path.name == "run.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "forgeproof-0.1"
