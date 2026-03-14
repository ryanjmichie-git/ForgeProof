"""Tests for the ForgeProof packer + RPB integration."""

import sys
import tempfile
from pathlib import Path

from forgeproof.models import (
    CommandResult,
    EvalScorecard,
    FileChange,
    IssueInfo,
    Plan,
    PlanStep,
    Requirement,
    RunState,
)
from forgeproof.provenance.packer import build_staging_directory, sign_and_pack


def test_build_staging_directory():
    """Verify staging directory has expected structure."""
    state = RunState(
        issue=IssueInfo(
            project_id=1,
            issue_iid=42,
            issue_title="Add CSV export",
            issue_body="Export todos as CSV",
        ),
        plan=Plan(
            requirements=[Requirement(id="REQ-1", description="CSV endpoint")],
            steps=[PlanStep(step=1, action="create", file_path="src/export.py", description="Add export")],
        ),
        file_changes=[
            FileChange(path="src/export.py", content="def export(): pass\n", action="create"),
            FileChange(path="tests/test_export.py", content="def test_export(): assert True\n", action="create"),
        ],
        evaluation=EvalScorecard(
            deterministic_pass=True,
            command_results=[
                CommandResult(name="tests", command="pytest -q", exit_code=0, stdout="1 passed"),
            ],
            requirements_coverage=90.0,
            review_ready=True,
        ),
    )

    with tempfile.TemporaryDirectory() as tmp:
        staging_dir = Path(tmp) / "staging"
        result = build_staging_directory(state, work_dir=staging_dir)

        # Check RPB required files
        assert (result / "MANIFEST.json").is_file()
        assert (result / "HASHES.json").is_file()
        assert (result / "POLICY.json").is_file()

        # Check ForgeProof structure
        assert (result / "SOURCE" / "src" / "export.py").is_file()
        assert (result / "SOURCE" / "tests" / "test_export.py").is_file()
        assert (result / "inputs" / "issue.json").is_file()
        assert (result / "plans" / "plan.json").is_file()
        assert (result / "evaluation" / "scorecard.json").is_file()
        assert (result / "EVIDENCE" / "TESTS" / "tests_stdout.txt").is_file()
        assert (result / "VERIFY" / "verify_instructions.txt").is_file()


def test_sign_and_pack():
    """Verify full pack creation with signing."""
    state = RunState(
        issue=IssueInfo(issue_title="Test issue"),
        file_changes=[
            FileChange(path="hello.py", content="print('hello')\n"),
        ],
    )

    # Find the RPB dev key
    rpb_root = Path(__file__).resolve().parents[1] / "Replication-Pack"
    key_path = rpb_root / "devkey.ed25519"
    if not key_path.exists():
        import pytest
        pytest.skip("RPB devkey.ed25519 not found")

    with tempfile.TemporaryDirectory() as tmp:
        staging_dir = Path(tmp) / "staging"
        staging = build_staging_directory(state, work_dir=staging_dir)

        out_path = Path(tmp) / "test.rpack"
        result = sign_and_pack(staging, key_path, out_path)

        assert result.exists()
        assert result.stat().st_size > 0

        # Verify the pack with RPB
        rpb_str = str(rpb_root)
        if rpb_str not in sys.path:
            sys.path.insert(0, rpb_str)

        from internal.rpb.pack_reader import extract_rpack  # type: ignore[import-untyped]
        from internal.rpb.verify_signatures import verify_pack_directory  # type: ignore[import-untyped]

        extract_dir = Path(tmp) / "extracted"
        extract_dir.mkdir()
        extract_rpack(str(result), str(extract_dir))

        pub_key_path = str(extract_dir / "SIGNATURES" / "signer-1.pub")
        vr = verify_pack_directory(str(extract_dir), pubkey_path=pub_key_path)
        assert vr.result.verified, f"Pack verification failed: {vr.result.failed_checks}"
