"""Tests for the ForgeProof Lite commit provenance script."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def test_capture_commit_metadata_returns_dict():
    """Verify _capture_commit_metadata returns expected keys."""
    from scripts.forge_commit import _capture_commit_metadata

    git_responses = {
        ("log", "-1", "--format=%H"): "abc123def456789012345678901234567890abcd",
        ("log", "-1", "--format=%P"): "parent789012345678901234567890abcdef012345",
        ("log", "-1", "--format=%an"): "Test Author",
        ("log", "-1", "--format=%ae"): "test@example.com",
        ("log", "-1", "--format=%aI"): "2026-03-22T12:00:00-04:00",
        ("log", "-1", "--format=%s"): "feat: test commit",
        ("rev-parse", "--abbrev-ref", "HEAD"): "hackathon-native",
        ("diff-tree", "--root", "--no-commit-id", "-r", "--diff-filter=AMDRT", "HEAD"): "",
    }

    def mock_git(*args):
        return git_responses.get(args, "")

    with patch("scripts.forge_commit._git", side_effect=mock_git):
        meta = _capture_commit_metadata()

    assert meta["commit_sha"] == "abc123def456789012345678901234567890abcd"
    assert meta["author"] == "Test Author"
    assert meta["branch"] == "hackathon-native"
    assert meta["schema_version"] == "forgeproof-lite-0.1"
    assert "changed_files" in meta


def test_changed_files_parsing_statuses():
    """Verify _parse_changed_files handles A/M/D statuses."""
    from scripts.forge_commit import _parse_changed_files

    diff_output = "A\tsrc/new_file.py\nM\tsrc/existing.py\nD\tsrc/old.py"

    with patch("scripts.forge_commit.sha256_file", return_value="abc123"):
        files = _parse_changed_files(diff_output, Path("/nonexistent_repo"))

    assert len(files) == 3

    added = next(f for f in files if f["status"] == "A")
    assert added["path"] == "src/new_file.py"

    deleted = next(f for f in files if f["status"] == "D")
    assert deleted["sha256"] is None


def test_deleted_file_has_null_hash():
    """Deleted files should have sha256: null."""
    from scripts.forge_commit import _parse_changed_files

    diff_output = "D\tremoved.py"
    files = _parse_changed_files(diff_output, Path("/nonexistent_repo"))

    assert len(files) == 1
    assert files[0]["sha256"] is None
    assert files[0]["status"] == "D"


def test_empty_diff_returns_empty_list():
    """Empty diff output should return empty list."""
    from scripts.forge_commit import _parse_changed_files

    files = _parse_changed_files("", Path("/repo"))
    assert files == []


def test_recursion_guard_detects_provenance_commits():
    """Should return True for provenance: commits."""
    from scripts.forge_commit import _is_provenance_commit

    with patch("scripts.forge_commit._git", return_value="provenance: sign abc123"):
        assert _is_provenance_commit() is True

    with patch("scripts.forge_commit._git", return_value="feat: add feature"):
        assert _is_provenance_commit() is False


def test_recursion_guard_partial_match():
    """Should not match 'provenance' without the colon prefix."""
    from scripts.forge_commit import _is_provenance_commit

    with patch("scripts.forge_commit._git", return_value="fix provenance tracking"):
        assert _is_provenance_commit() is False


def test_build_and_sign_produces_rpack(tmp_path):
    """Integration test: full flow produces a valid .rpack file."""
    from scripts.forge_commit import _build_and_sign_rpack

    commit_data = {
        "schema_version": "forgeproof-lite-0.1",
        "commit_sha": "abc123def456789012345678901234567890abcd",
        "parent_sha": "parent789012345678901234567890abcdef012345",
        "author": "Test",
        "email": "test@test.com",
        "timestamp": "2026-03-22T12:00:00Z",
        "message": "test commit",
        "branch": "main",
        "changed_files": [],
    }

    devkey = tmp_path / "devkey.ed25519"
    devkey.write_bytes(os.urandom(32))

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    rpack_path = _build_and_sign_rpack(commit_data, devkey, output_dir)

    assert rpack_path is not None
    assert rpack_path.exists()
    assert rpack_path.suffix == ".rpack"
    assert rpack_path.stat().st_size > 0


def test_rpack_is_verifiable(tmp_path):
    """The produced .rpack should pass RPB verification."""
    import sys
    rpack_root = Path(__file__).resolve().parents[1] / "Replication-Pack"
    sys.path.insert(0, str(rpack_root))

    from scripts.forge_commit import _build_and_sign_rpack
    from internal.rpb.verify_signatures import verify_pack_directory
    from internal.rpb.pack_reader import extract_rpack

    commit_data = {
        "schema_version": "forgeproof-lite-0.1",
        "commit_sha": "deadbeef12345678901234567890abcdef012345",
        "parent_sha": None,
        "author": "Verifier",
        "email": "v@test.com",
        "timestamp": "2026-03-22T12:00:00Z",
        "message": "initial commit",
        "branch": "main",
        "changed_files": [],
    }

    devkey = tmp_path / "devkey.ed25519"
    devkey.write_bytes(os.urandom(32))

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    rpack_path = _build_and_sign_rpack(commit_data, devkey, output_dir)

    # Extract and verify
    extract_dir = tmp_path / "extracted"
    extract_rpack(rpack_path, extract_dir)
    result = verify_pack_directory(extract_dir, pubkey_path=devkey)

    assert result.verified is True
    assert "CLAIM-INTEGRITY-001" in result.claims_verified


def test_null_parent_sha_for_initial_commit():
    """Initial commits should have parent_sha as None."""
    from scripts.forge_commit import _capture_commit_metadata

    git_responses = {
        ("log", "-1", "--format=%H"): "abc123",
        ("log", "-1", "--format=%P"): "",
        ("log", "-1", "--format=%an"): "Author",
        ("log", "-1", "--format=%ae"): "a@b.com",
        ("log", "-1", "--format=%aI"): "2026-03-22T12:00:00Z",
        ("log", "-1", "--format=%s"): "initial",
        ("rev-parse", "--abbrev-ref", "HEAD"): "main",
        ("diff-tree", "--root", "--no-commit-id", "-r", "--diff-filter=AMDRT", "HEAD"): "",
    }

    def mock_git(*args):
        return git_responses.get(args, "")

    with patch("scripts.forge_commit._git", side_effect=mock_git):
        meta = _capture_commit_metadata()

    assert meta["parent_sha"] is None
