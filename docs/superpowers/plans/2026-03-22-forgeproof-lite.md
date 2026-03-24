# ForgeProof Lite Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Post-commit git hook that signs commit provenance into verifiable .rpack bundles using existing RPB Ed25519 signing.

**Architecture:** A shell hook calls a Python script that captures git metadata, writes it to a temp directory, feeds it through RPB's staging/signing/packing pipeline, and outputs to `provenance/`. Uses existing RPB code — no new dependencies.

**Tech Stack:** Python 3.11, git CLI, existing RPB modules (Ed25519, SHA-256, TAR packing)

**Spec:** `docs/superpowers/specs/2026-03-22-forgeproof-lite-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scripts/forge_commit.py` | Create | Main script: capture git metadata, stage, sign, pack |
| `.githooks/post-commit` | Create | Shell hook: calls forge_commit.py |
| `provenance/.gitkeep` | Create | Ensure provenance directory is tracked |
| `tests/test_forge_commit.py` | Create | Tests for forge_commit.py |
| `README.md` | Modify | Add provenance verification section |

---

### Task 1: Create branch and directory structure

**Files:**
- Create: `provenance/.gitkeep`
- Create: `.githooks/post-commit`

- [ ] **Step 1: Create hackathon-native branch**

```bash
git checkout -b hackathon-native
```

- [ ] **Step 2: Create provenance directory**

```bash
mkdir -p provenance
touch provenance/.gitkeep
```

- [ ] **Step 3: Create the post-commit hook**

Create `.githooks/post-commit`:

```bash
#!/bin/bash
# ForgeProof Lite: sign commit provenance after each commit
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Skip provenance commits to prevent infinite recursion
COMMIT_MSG="$(git log -1 --format=%s)"
if echo "$COMMIT_MSG" | grep -q "^provenance:"; then
    exit 0
fi

python "$REPO_ROOT/scripts/forge_commit.py" 2>>"$REPO_ROOT/.forge-commit.log" || true
```

- [ ] **Step 4: Make hook executable**

```bash
chmod +x .githooks/post-commit
```

- [ ] **Step 5: Add .forge-commit.log to .gitignore**

Append `.forge-commit.log` to `.gitignore`.

- [ ] **Step 6: Commit**

```bash
git add provenance/.gitkeep .githooks/post-commit .gitignore
git commit -m "chore: add post-commit hook scaffold and provenance directory"
```

---

### Task 2: Write failing tests for forge_commit.py

**Files:**
- Create: `tests/test_forge_commit.py`

- [ ] **Step 1: Write test file with core tests**

Create `tests/test_forge_commit.py`:

```python
"""Tests for the ForgeProof Lite commit provenance script."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


def test_capture_commit_metadata_returns_dict(tmp_path):
    """Verify _capture_commit_metadata returns expected keys."""
    # Will import after implementation exists
    from scripts.forge_commit import _capture_commit_metadata

    # Mock git commands to return known values
    with patch("scripts.forge_commit._git") as mock_git:
        mock_git.side_effect = lambda *args: {
            ("log", "-1", "--format=%H"): "abc123def456",
            ("log", "-1", "--format=%P"): "parent789",
            ("log", "-1", "--format=%an"): "Test Author",
            ("log", "-1", "--format=%ae"): "test@example.com",
            ("log", "-1", "--format=%aI"): "2026-03-22T12:00:00-04:00",
            ("log", "-1", "--format=%s"): "feat: test commit",
            ("rev-parse", "--abbrev-ref", "HEAD"): "hackathon-native",
            ("diff-tree", "--root", "--no-commit-id", "-r", "--diff-filter=AMDRT", "HEAD"): "",
        }.get(args, "")

        meta = _capture_commit_metadata()

    assert meta["commit_sha"] == "abc123def456"
    assert meta["author"] == "Test Author"
    assert meta["branch"] == "hackathon-native"
    assert meta["schema_version"] == "forgeproof-lite-0.1"
    assert "changed_files" in meta


def test_changed_files_parsing():
    """Verify _parse_changed_files handles A/M/D statuses."""
    from scripts.forge_commit import _parse_changed_files

    diff_output = "A\tsrc/new_file.py\nM\tsrc/existing.py\nD\tsrc/old.py"

    with patch("scripts.forge_commit.sha256_file") as mock_hash:
        mock_hash.return_value = "abc123"
        files = _parse_changed_files(diff_output, Path("/repo"))

    assert len(files) == 3
    added = next(f for f in files if f["status"] == "A")
    assert added["path"] == "src/new_file.py"

    deleted = next(f for f in files if f["status"] == "D")
    assert deleted["sha256"] is None


def test_deleted_file_has_null_hash():
    """Deleted files should have sha256: null."""
    from scripts.forge_commit import _parse_changed_files

    diff_output = "D\tremoved.py"
    files = _parse_changed_files(diff_output, Path("/repo"))

    assert files[0]["sha256"] is None
    assert files[0]["status"] == "D"


def test_recursion_guard():
    """Should return True for provenance: commits."""
    from scripts.forge_commit import _is_provenance_commit

    with patch("scripts.forge_commit._git") as mock_git:
        mock_git.return_value = "provenance: sign abc123"
        assert _is_provenance_commit() is True

        mock_git.return_value = "feat: add feature"
        assert _is_provenance_commit() is False


def test_build_and_sign_produces_rpack(tmp_path):
    """Integration test: full flow produces a valid .rpack file."""
    from scripts.forge_commit import _build_and_sign_rpack

    commit_data = {
        "schema_version": "forgeproof-lite-0.1",
        "commit_sha": "abc123def456",
        "parent_sha": "parent789",
        "author": "Test",
        "email": "test@test.com",
        "timestamp": "2026-03-22T12:00:00Z",
        "message": "test commit",
        "branch": "main",
        "changed_files": [],
    }

    devkey = tmp_path / "devkey.ed25519"
    import os
    devkey.write_bytes(os.urandom(32))

    output_dir = tmp_path / "out"
    output_dir.mkdir()

    rpack_path = _build_and_sign_rpack(commit_data, devkey, output_dir)

    assert rpack_path is not None
    assert rpack_path.exists()
    assert rpack_path.suffix == ".rpack"
    assert rpack_path.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_forge_commit.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts'` or `ImportError`

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_forge_commit.py
git commit -m "test: add failing tests for forge_commit.py"
```

---

### Task 3: Implement forge_commit.py

**Files:**
- Create: `scripts/forge_commit.py`
- Create: `scripts/__init__.py`

- [ ] **Step 1: Create scripts package init**

Create `scripts/__init__.py` (empty file for importability):

```python
```

- [ ] **Step 2: Write forge_commit.py**

Create `scripts/forge_commit.py`:

```python
"""ForgeProof Lite: sign commit provenance into .rpack bundles.

Post-commit hook script. Captures git metadata and file hashes,
signs with Ed25519 via RPB, outputs to provenance/ directory.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# --- Path setup: make RPB importable ---
REPO_ROOT = Path(__file__).resolve().parents[1]
RPACK_ROOT = REPO_ROOT / "Replication-Pack"
sys.path.insert(0, str(RPACK_ROOT))

from internal.hash import sha256_file  # noqa: E402
from internal.rpb.pack_writer import create_rpack  # noqa: E402
from internal.rpb.sign import write_signatures  # noqa: E402
from internal.rpb.staging import finalize_pack_metadata  # noqa: E402
from internal.canon import dumps_canonical  # noqa: E402

log = logging.getLogger("forge_commit")

DEVKEY_PATH = RPACK_ROOT / "devkey.ed25519"
PROVENANCE_DIR = REPO_ROOT / "provenance"


def _git(*args: str) -> str:
    """Run a git command and return stripped stdout."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    return result.stdout.strip()


def _is_provenance_commit() -> bool:
    """Check if the latest commit is a provenance commit (recursion guard)."""
    msg = _git("log", "-1", "--format=%s")
    return msg.startswith("provenance:")


def _parse_changed_files(diff_output: str, repo_root: Path) -> list[dict]:
    """Parse git diff-tree output into file change records."""
    files = []
    for line in diff_output.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, path = parts[0].strip(), parts[1].strip()

        if status == "D":
            file_hash = None
        else:
            file_path = repo_root / path
            try:
                file_hash = sha256_file(file_path) if file_path.is_file() else None
            except Exception:
                file_hash = None

        files.append({"path": path, "sha256": file_hash, "status": status})
    return files


def _capture_commit_metadata() -> dict:
    """Capture metadata about the current HEAD commit."""
    commit_sha = _git("log", "-1", "--format=%H")
    parent_sha = _git("log", "-1", "--format=%P") or None
    author = _git("log", "-1", "--format=%an")
    email = _git("log", "-1", "--format=%ae")
    timestamp = _git("log", "-1", "--format=%aI")
    message = _git("log", "-1", "--format=%s")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")

    diff_output = _git("diff-tree", "--root", "--no-commit-id", "-r",
                       "--diff-filter=AMDRT", "HEAD")
    changed_files = _parse_changed_files(diff_output, REPO_ROOT)

    return {
        "schema_version": "forgeproof-lite-0.1",
        "commit_sha": commit_sha,
        "parent_sha": parent_sha,
        "author": author,
        "email": email,
        "timestamp": timestamp,
        "message": message,
        "branch": branch,
        "changed_files": changed_files,
    }


def _build_and_sign_rpack(
    commit_data: dict,
    devkey_path: Path,
    output_dir: Path,
) -> Path | None:
    """Build staging directory, sign, pack into .rpack."""
    staging = Path(tempfile.mkdtemp(prefix="forgeproof_lite_"))

    try:
        # Create staging structure manually (simpler than prepare_staging_directory
        # since our input is a single JSON file, not a directory tree)
        source_dir = staging / "SOURCE"
        source_dir.mkdir()
        sig_dir = staging / "SIGNATURES"
        sig_dir.mkdir()
        verify_dir = staging / "VERIFY"
        verify_dir.mkdir()

        # Write commit metadata
        commit_json = source_dir / "commit.json"
        commit_json.write_bytes(dumps_canonical(commit_data))

        # Write verification instructions
        (verify_dir / "verify_instructions.txt").write_text(
            "Verify: rpb verify <pack.rpack> --pubkey devkey.ed25519\n",
            encoding="utf-8",
        )

        # Write POLICY.json (P0 integrity only)
        policy = {
            "schema_version": "rpb-policy-0.1",
            "policy_id": "forgeproof-lite-default",
            "policy_version": "0.1",
            "profiles": {"P0": True, "P1": False, "P2": False, "P3": False},
            "signature_thresholds": {"P0": 1, "P1": 1, "P2": 1, "P3": 2},
            "requirements": {
                "P0": {
                    "must_include_paths": ["MANIFEST.json", "HASHES.json", "SIGNATURES/"],
                    "must_have_commands": [],
                    "must_have_evidence_types": [],
                    "must_reference_spec_properties": False,
                },
            },
        }
        (staging / "POLICY.json").write_bytes(dumps_canonical(policy))

        # Write initial MANIFEST.json
        short_sha = commit_data["commit_sha"][:12]
        manifest = {
            "schema_version": "rpb-manifest-0.1",
            "pack_id": f"forgeproof-lite-{short_sha}",
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "producer": {"name": "forgeproof-lite", "version": "0.1.0", "build": "post-commit-hook"},
            "subject": {
                "name": "commit-provenance",
                "version": commit_data["commit_sha"][:8],
                "vcs": {"type": "git", "commit": commit_data["commit_sha"], "branch": commit_data["branch"]},
            },
            "claims": [
                {"claim_id": "CLAIM-INTEGRITY-001", "profile": "P0",
                 "label": "Integrity: commit provenance matches signed hashes", "properties": []},
            ],
            "environment": {"type": "local", "image_digest": "sha256:" + "0" * 64, "os_arch": "local", "toolchain": []},
            "commands": {"build": [], "tests": [], "proofs": []},
            "artifacts": [],
            "evidence": [],
            "policy": {"policy_id": "forgeproof-lite-default", "policy_version": "0.1", "policy_sha256": ""},
            "signing": {"root_digest_sha256": "0" * 64, "signers": []},
            "redactions": [],
        }
        (staging / "MANIFEST.json").write_bytes(dumps_canonical(manifest))

        # Write empty HASHES.json (finalize will rebuild)
        (staging / "HASHES.json").write_bytes(dumps_canonical(
            {"hash_algo": "sha256", "generated_utc": "1970-01-01T00:00:00Z", "files": []}
        ))

        # Finalize: rebuilds HASHES.json and MANIFEST.json with correct root digest
        finalize_pack_metadata(staging)

        # Sign with Ed25519
        write_signatures(staging, devkey_path)

        # Pack into .rpack
        rpack_name = f"{short_sha}.rpack"
        rpack_path = output_dir / rpack_name
        create_rpack(staging, rpack_path)

        return rpack_path

    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    """Entry point for post-commit hook."""
    if _is_provenance_commit():
        return

    if not DEVKEY_PATH.exists():
        log.warning("No devkey found at %s; skipping provenance signing", DEVKEY_PATH)
        return

    PROVENANCE_DIR.mkdir(exist_ok=True)

    try:
        commit_data = _capture_commit_metadata()
        rpack_path = _build_and_sign_rpack(commit_data, DEVKEY_PATH, PROVENANCE_DIR)
        if rpack_path:
            short_sha = commit_data["commit_sha"][:12]
            print(f"ForgeProof: signed provenance -> provenance/{short_sha}.rpack")
    except Exception:
        log.exception("ForgeProof Lite: provenance signing failed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run tests to verify they pass**

```bash
python -m pytest tests/test_forge_commit.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 4: Run full test suite to check for regressions**

```bash
python -m pytest tests/ -q --tb=short
```

Expected: All 137+ tests pass

- [ ] **Step 5: Lint check**

```bash
python -m ruff check scripts/ tests/test_forge_commit.py
```

Expected: All checks passed

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/forge_commit.py
git commit -m "feat: implement forge_commit.py post-commit provenance signing"
```

---

### Task 4: Verify end-to-end flow

**Files:** None (verification only)

- [ ] **Step 1: Enable the hook**

```bash
git config core.hooksPath .githooks
```

- [ ] **Step 2: Make a test commit**

```bash
echo "# test" >> provenance/.gitkeep
git add provenance/.gitkeep
git commit -m "test: verify post-commit hook"
```

Expected: Console output `ForgeProof: signed provenance -> provenance/<sha>.rpack`

- [ ] **Step 3: Verify .rpack was created**

```bash
ls -la provenance/*.rpack
```

Expected: One .rpack file exists

- [ ] **Step 4: Verify the .rpack with RPB**

```bash
cd Replication-Pack && python cmd/rpb.py verify ../provenance/*.rpack --pubkey devkey.ed25519 --json
```

Expected: `{"verified": true, "claims_verified": ["CLAIM-INTEGRITY-001"], ...}`

- [ ] **Step 5: Commit the provenance file**

```bash
git add provenance/
git commit -m "provenance: sign latest commits"
```

Expected: No new .rpack created (recursion guard skips provenance: commits)

- [ ] **Step 6: Verify recursion guard worked**

```bash
ls provenance/*.rpack | wc -l
```

Expected: Still just 1 .rpack file (no new one from the provenance commit)

---

### Task 5: Update README and push

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add provenance section to README**

Add after the "Tech Stack" section in README.md:

```markdown
## Provenance Verification (Hackathon Branch)

On the `hackathon-native` branch, every commit is automatically signed into a tamper-evident `.rpack` provenance bundle via a post-commit git hook.

### Setup

```bash
git config core.hooksPath .githooks
```

### Verify a Commit's Provenance

```bash
cd Replication-Pack
python cmd/rpb.py verify ../provenance/<sha>.rpack --pubkey devkey.ed25519 --json
```

### What's Inside Each .rpack

- `SOURCE/commit.json` — Commit SHA, author, timestamp, message, changed file hashes
- `MANIFEST.json` — Pack metadata with integrity claim
- `HASHES.json` — SHA-256 hashes of all bundle files
- `SIGNATURES/` — Ed25519 signature over the root digest
- `VERIFY/` — Verification instructions
```

- [ ] **Step 2: Commit and push to both remotes**

```bash
git add README.md
git commit -m "docs: add provenance verification section to README"
git push personal hackathon-native
git push hackathon hackathon-native
```

---

## Verification Checklist

After all tasks complete:

1. `provenance/` directory contains at least one `.rpack` file
2. `rpb verify` returns `verified: true` for each .rpack
3. Post-commit hook runs silently on normal commits (~1s)
4. Recursion guard prevents infinite loop on `provenance:` commits
5. All existing tests still pass (137+)
6. Code pushed to both remotes on `hackathon-native` branch
