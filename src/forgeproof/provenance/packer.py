"""Build ForgeProof staging directory and produce signed .rpack via RPB."""

from __future__ import annotations

import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from forgeproof.config import ForgeProofConfig
from forgeproof.models import RunState

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RPB bootstrap: add Replication-Pack root to sys.path so we can import it.
# ---------------------------------------------------------------------------

_RPB_ROOT = Path(__file__).resolve().parents[3] / "Replication-Pack"


def _ensure_rpb_importable() -> None:
    rpb_str = str(_RPB_ROOT)
    if rpb_str not in sys.path:
        sys.path.insert(0, rpb_str)


def _rpb_staging():
    _ensure_rpb_importable()
    from internal.rpb import staging  # type: ignore[import-untyped]
    return staging


def _rpb_sign():
    _ensure_rpb_importable()
    from internal.rpb import sign  # type: ignore[import-untyped]
    return sign


def _rpb_pack_writer():
    _ensure_rpb_importable()
    from internal.rpb import pack_writer  # type: ignore[import-untyped]
    return pack_writer


def _rpb_canon():
    _ensure_rpb_importable()
    from internal import canon  # type: ignore[import-untyped]
    return canon


# ---------------------------------------------------------------------------
# Staging directory builder
# ---------------------------------------------------------------------------

def build_staging_directory(
    state: RunState,
    *,
    prompts_dir: Path | None = None,
    outputs_dir: Path | None = None,
    decision_log_path: Path | None = None,
    work_dir: Path | None = None,
) -> Path:
    """Create a ForgeProof staging directory ready for RPB finalization.

    Returns the path to the staging directory.
    """
    staging = _rpb_staging()
    canon = _rpb_canon()

    staging_root = Path(work_dir or tempfile.mkdtemp(prefix="forgeproof_staging_"))
    log.info("Building staging directory at %s", staging_root)

    # Create standard RPB directories
    (staging_root / "SOURCE").mkdir(parents=True, exist_ok=True)
    (staging_root / "SIGNATURES").mkdir(parents=True, exist_ok=True)
    (staging_root / "EVIDENCE" / "TESTS").mkdir(parents=True, exist_ok=True)
    (staging_root / "VERIFY").mkdir(parents=True, exist_ok=True)
    (staging_root / "FORGEPROOF").mkdir(parents=True, exist_ok=True)

    # Write verification instructions
    (staging_root / "VERIFY" / "verify_instructions.txt").write_text(
        "Offline verify: run `rpb verify <pack.rpack>` or use scripts/verify_pack.py\n"
        "ForgeProof metadata is in FORGEPROOF/run.json\n"
        "Decision log with hash chain is in FORGEPROOF/decision_log.jsonl\n",
        encoding="utf-8",
    )

    # Write generated source files
    for fc in state.file_changes:
        dest = staging_root / "SOURCE" / fc.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(fc.content, encoding="utf-8")

    # Write issue snapshot
    inputs_dir = staging_root / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    (inputs_dir / "issue.json").write_text(
        json.dumps(state.issue.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Write plan
    if state.plan:
        plans_dir = staging_root / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        (plans_dir / "plan.json").write_text(
            json.dumps(state.plan.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Write evaluation scorecard
    if state.evaluation:
        eval_dir = staging_root / "evaluation"
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "scorecard.json").write_text(
            json.dumps(state.evaluation.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Write individual command outputs as evidence
        for cr in state.evaluation.command_results:
            evidence_file = staging_root / "EVIDENCE" / "TESTS" / f"{cr.name}_stdout.txt"
            evidence_file.write_text(cr.stdout, encoding="utf-8")
            stderr_file = staging_root / "EVIDENCE" / "TESTS" / f"{cr.name}_stderr.txt"
            stderr_file.write_text(cr.stderr, encoding="utf-8")

    # Copy prompts/outputs directories
    if prompts_dir and prompts_dir.is_dir():
        shutil.copytree(prompts_dir, staging_root / "prompts", dirs_exist_ok=True)
    if outputs_dir and outputs_dir.is_dir():
        shutil.copytree(outputs_dir, staging_root / "outputs", dirs_exist_ok=True)

    # Copy decision log
    if decision_log_path and decision_log_path.is_file():
        shutil.copy2(decision_log_path, staging_root / "FORGEPROOF" / "decision_log.jsonl")

    # Write RPB POLICY.json
    policy: dict[str, Any] = staging.DEFAULT_POLICY_FALLBACK.copy()
    (staging_root / "POLICY.json").write_bytes(canon.dumps_canonical(policy))

    # Write RPB MANIFEST.json skeleton
    manifest = _build_rpb_manifest(state, policy, canon)
    (staging_root / "MANIFEST.json").write_bytes(canon.dumps_canonical(manifest))

    # Let RPB finalize: rebuild HASHES.json, root digest, artifacts list
    staging.finalize_pack_metadata(staging_root)

    log.info("Staging directory ready: %s", staging_root)
    return staging_root


def sign_and_pack(
    staging_dir: Path,
    key_path: Path,
    output_path: Path,
) -> Path:
    """Sign the staging directory and create the .rpack archive.

    RPB's write_signatures internally loads the pack, computes the root digest,
    signs it, and writes SIGNATURES/. The signature covers MANIFEST+HASHES+POLICY,
    so we must NOT re-finalize after signing (that would change HASHES.json and
    invalidate the signature).
    """
    rpb_sign = _rpb_sign()
    rpb_pw = _rpb_pack_writer()

    log.info("Signing pack with key %s", key_path)
    rpb_sign.write_signatures(staging_dir, key_path)

    log.info("Creating .rpack archive at %s", output_path)
    rpb_pw.create_rpack(staging_dir, output_path)

    log.info("Pack created: %s (%d bytes)", output_path, output_path.stat().st_size)
    return output_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_rpb_manifest(
    state: RunState,
    policy: dict[str, Any],
    canon: Any,
) -> dict[str, Any]:
    """Build an RPB-compatible MANIFEST.json with ForgeProof extensions."""
    from internal.hash import sha256_bytes  # type: ignore[import-untyped]

    policy_sha256 = sha256_bytes(canon.dumps_canonical(policy))

    claims = [
        {
            "claim_id": "CLAIM-INTEGRITY-001",
            "profile": "P0",
            "label": "Integrity: contents match signed hashes",
            "properties": [],
        },
    ]

    # Add P2 claim if we have test evidence
    if state.evaluation and state.evaluation.command_results:
        claims.append({
            "claim_id": "CLAIM-TESTED-001",
            "profile": "P2",
            "label": "Tested: evaluation commands executed with results",
            "properties": [],
        })

    # Build test commands list for RPB
    test_commands: list[str] = []
    evidence: list[dict[str, Any]] = []
    if state.evaluation:
        for cr in state.evaluation.command_results:
            test_commands.append(cr.command)
            evidence.append({
                "evidence_id": f"EV-{cr.name.upper()}-001",
                "type": "tests",
                "command": cr.command,
                "exit_code": cr.exit_code,
                "stdout_path": f"EVIDENCE/TESTS/{cr.name}_stdout.txt",
                "stderr_path": f"EVIDENCE/TESTS/{cr.name}_stderr.txt",
            })

    return {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": state.run_id,
        "created_utc": "1970-01-01T00:00:00Z",
        "producer": {
            "name": "forgeproof",
            "version": "0.1.0",
            "build": "hackathon-mvp",
        },
        "subject": {
            "name": state.issue.issue_title or "forgeproof-run",
            "version": "0.0.0",
            "vcs": {
                "type": "git",
                "repo_url": "",
                "commit": state.git.base_commit,
                "dirty": False,
            },
        },
        "claims": claims,
        "environment": {
            "type": "container",
            "image_digest": f"sha256:{'0' * 64}",
            "os_arch": "linux/amd64",
            "toolchain": [],
        },
        "commands": {
            "build": [],
            "tests": test_commands,
            "proofs": [],
        },
        "artifacts": [],
        "evidence": evidence,
        "policy": {
            "policy_id": str(policy.get("policy_id", "default-mvp")),
            "policy_version": str(policy.get("policy_version", "0.1.0")),
            "policy_sha256": policy_sha256,
        },
        "signing": {
            "root_digest_sha256": "0" * 64,
            "signers": [],
        },
        "redactions": [
            {"pattern": ".env", "reason": "Prevent secret leakage"},
            {"pattern": "**/*_key*", "reason": "Prevent private key inclusion"},
        ],
    }
