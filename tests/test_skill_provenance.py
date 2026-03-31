# tests/test_skill_provenance.py
import json
import subprocess
import sys
from pathlib import Path

LIB_DIR = str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib")
sys.path.insert(0, LIB_DIR)

def _setup_run_state(tmp_path):
    """Create minimal last-run.json + decision-log.jsonl for testing."""
    src_dir = tmp_path / "repo" / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "main.py").write_text("print('hello')")

    run_state = {
        "issue_number": 1,
        "issue_title": "Test issue",
        "repo": "test/repo",
        "branch": "forgeproof/issue-1",
        "files_changed": ["src/main.py"],
        "requirements": ["REQ-1"],
        "requirements_met": 1,
        "requirements_total": 1,
        "tests_passed": 1,
        "tests_total": 1,
        "rpack_path": ".forgeproof/issue-1.rpack",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    fp_dir = tmp_path / "repo" / ".forgeproof"
    fp_dir.mkdir(parents=True)
    (fp_dir / "last-run.json").write_text(json.dumps(run_state))
    (fp_dir / "decision-log.jsonl").write_text(
        json.dumps({"seq": 1, "phase": "test", "action": "test", "detail": "test", "prev_hash": "0" * 64, "entry_hash": "a" * 64, "timestamp": "2026-01-01T00:00:00Z"}) + "\n"
    )
    return tmp_path / "repo"

def test_provenance_build_creates_rpack(tmp_path):
    repo = _setup_run_state(tmp_path)
    fp_dir = repo / ".forgeproof"
    output = fp_dir / "issue-1.rpack"
    result = subprocess.run(
        [sys.executable, f"{LIB_DIR}/provenance.py", "build",
         "--run-state", str(fp_dir / "last-run.json"),
         "--decision-log", str(fp_dir / "decision-log.jsonl"),
         "--output", str(output),
         "--repo-root", str(repo)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output.exists()
    import tarfile
    assert tarfile.is_tarfile(output)

def test_provenance_build_rpack_contains_manifest(tmp_path):
    repo = _setup_run_state(tmp_path)
    fp_dir = repo / ".forgeproof"
    output = fp_dir / "issue-1.rpack"
    subprocess.run(
        [sys.executable, f"{LIB_DIR}/provenance.py", "build",
         "--run-state", str(fp_dir / "last-run.json"),
         "--decision-log", str(fp_dir / "decision-log.jsonl"),
         "--output", str(output),
         "--repo-root", str(repo)],
        capture_output=True, text=True
    )
    from rpb.pack_reader import extract_rpack
    extract_dir = tmp_path / "extracted"
    extract_rpack(output, extract_dir)
    assert (extract_dir / "MANIFEST.json").exists()
    assert (extract_dir / "HASHES.json").exists()
    assert (extract_dir / "POLICY.json").exists()
    assert (extract_dir / "SIGNATURES").is_dir()
