"""Tests for evaluation phase logic."""

import subprocess
from unittest.mock import patch

from forgeproof.models import FileChange
from forgeproof.phases.evaluate import (
    _detect_target_subdir,
    _run_command,
    _strip_prefix,
)


# -- _detect_target_subdir --

def test_detect_target_subdir_empty(tmp_path):
    result = _detect_target_subdir([], tmp_path)
    assert result == tmp_path


def test_detect_target_subdir_majority(tmp_path):
    """2/3 files in a subdir with pyproject.toml → returns subdir."""
    subdir = tmp_path / "demo" / "seed-repo"
    subdir.mkdir(parents=True)
    (subdir / "pyproject.toml").write_text("[project]", encoding="utf-8")

    changes = [
        FileChange(path="demo/seed-repo/src/main.py", content="x"),
        FileChange(path="demo/seed-repo/tests/test.py", content="y"),
        FileChange(path="tests/other.py", content="z"),
    ]
    result = _detect_target_subdir(changes, tmp_path)
    assert result == subdir


def test_detect_target_subdir_no_pyproject(tmp_path):
    """Subdir without pyproject.toml → returns repo root."""
    subdir = tmp_path / "demo" / "seed-repo"
    subdir.mkdir(parents=True)
    # No pyproject.toml

    changes = [
        FileChange(path="demo/seed-repo/src/main.py", content="x"),
        FileChange(path="demo/seed-repo/tests/test.py", content="y"),
    ]
    result = _detect_target_subdir(changes, tmp_path)
    assert result == tmp_path


def test_detect_target_subdir_all_root(tmp_path):
    """All files at root level → returns repo root."""
    changes = [
        FileChange(path="src/main.py", content="x"),
        FileChange(path="tests/test.py", content="y"),
    ]
    result = _detect_target_subdir(changes, tmp_path)
    assert result == tmp_path


def test_detect_target_subdir_single_file(tmp_path):
    """Single file in subdir → not enough for majority with 1 file."""
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "pyproject.toml").write_text("[project]", encoding="utf-8")

    changes = [FileChange(path="sub/main.py", content="x")]
    result = _detect_target_subdir(changes, tmp_path)
    # 1 file, 1 match → 1 > 1/2 so it should match
    assert result == subdir


# -- _strip_prefix --

def test_strip_prefix_with_subdir(tmp_path):
    prefix = tmp_path / "demo" / "seed-repo"
    result = _strip_prefix("demo/seed-repo/src/main.py", prefix, tmp_path)
    assert result.replace("\\", "/") == "src/main.py"


def test_strip_prefix_at_root(tmp_path):
    result = _strip_prefix("src/main.py", tmp_path, tmp_path)
    assert result == "src/main.py"


def test_strip_prefix_no_match(tmp_path):
    prefix = tmp_path / "other"
    result = _strip_prefix("different/path.py", prefix, tmp_path)
    assert result == "different/path.py"


# -- _run_command --

def test_run_command_success(tmp_path):
    cr = _run_command("echo_test", "echo hello", tmp_path)
    assert cr.exit_code == 0
    assert "hello" in cr.stdout
    assert cr.name == "echo_test"
    assert cr.duration_ms >= 0


def test_run_command_failure(tmp_path):
    cr = _run_command("fail_test", "exit 1", tmp_path)
    assert cr.exit_code == 1


def test_run_command_stderr(tmp_path):
    cr = _run_command("stderr_test", "echo error >&2", tmp_path)
    assert "error" in cr.stderr


def test_run_command_timeout(tmp_path):
    with patch("forgeproof.phases.evaluate.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 120)
        cr = _run_command("timeout_test", "sleep 999", tmp_path)
    assert cr.exit_code == -1
    assert "timed out" in cr.stderr.lower()
