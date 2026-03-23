"""ForgeProof Lite: sign commit provenance into .rpack bundles.

Post-commit hook script. Captures git metadata and file hashes,
signs with Ed25519 via RPB, outputs to provenance/ directory.
"""

from __future__ import annotations

import logging
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

from internal.canon import dumps_canonical  # noqa: E402
from internal.hash import sha256_file  # noqa: E402
from internal.rpb.pack_writer import create_rpack  # noqa: E402
from internal.rpb.sign import write_signatures  # noqa: E402
from internal.rpb.staging import finalize_pack_metadata  # noqa: E402

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
        # Create staging structure
        source_dir = staging / "SOURCE"
        source_dir.mkdir()
        (staging / "SIGNATURES").mkdir()
        verify_dir = staging / "VERIFY"
        verify_dir.mkdir()

        # Write commit metadata
        (source_dir / "commit.json").write_bytes(dumps_canonical(commit_data))

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
            "producer": {
                "name": "forgeproof-lite",
                "version": "0.1.0",
                "build": "post-commit-hook",
            },
            "subject": {
                "name": "commit-provenance",
                "version": commit_data["commit_sha"][:8],
                "vcs": {
                    "type": "git",
                    "commit": commit_data["commit_sha"],
                    "branch": commit_data.get("branch", "unknown"),
                },
            },
            "claims": [
                {
                    "claim_id": "CLAIM-INTEGRITY-001",
                    "profile": "P0",
                    "label": "Integrity: commit provenance matches signed hashes",
                    "properties": [],
                },
            ],
            "environment": {
                "type": "local",
                "image_digest": "sha256:" + "0" * 64,
                "os_arch": "local",
                "toolchain": [],
            },
            "commands": {"build": [], "tests": [], "proofs": []},
            "artifacts": [],
            "evidence": [],
            "policy": {
                "policy_id": "forgeproof-lite-default",
                "policy_version": "0.1",
                "policy_sha256": "",
            },
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
