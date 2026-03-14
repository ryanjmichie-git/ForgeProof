"""Build the ForgeProof-level run manifest (FORGEPROOF/run.json)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from forgeproof.models import RunState


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def build_run_manifest(state: RunState, staging_dir: Path) -> dict[str, Any]:
    """Build the ForgeProof run manifest from the current run state."""
    manifest: dict[str, Any] = {
        "schema_version": "forgeproof-0.1",
        "run_id": state.run_id,
        "created_utc": state.created_utc,
        "trigger": state.trigger.model_dump(),
        "source": {
            "project_id": state.issue.project_id,
            "issue_iid": state.issue.issue_iid,
            "issue_title": state.issue.issue_title,
        },
        "git": state.git.model_dump(),
        "phases": [p.model_dump() for p in state.phases],
    }

    # Inputs
    inputs: list[dict[str, Any]] = []
    for name in ("issue.json", "repo_context.json"):
        p = staging_dir / "inputs" / name
        if p.exists():
            inputs.append({
                "type": name.replace(".json", ""),
                "path": f"inputs/{name}",
                "sha256": _sha256_file(p),
            })
    manifest["inputs"] = inputs

    # Outputs (changed files)
    outputs: list[dict[str, Any]] = []
    source_dir = staging_dir / "SOURCE"
    if source_dir.is_dir():
        for f in sorted(source_dir.rglob("*")):
            if f.is_file():
                rel = f.relative_to(staging_dir)
                outputs.append({
                    "path": str(rel).replace("\\", "/"),
                    "sha256": _sha256_file(f),
                })
    manifest["outputs"] = outputs

    # Evaluation
    if state.evaluation:
        manifest["evaluation"] = state.evaluation.model_dump()

    # Audit
    dl_path = staging_dir / "FORGEPROOF" / "decision_log.jsonl"
    manifest["audit"] = {
        "decision_log_path": "FORGEPROOF/decision_log.jsonl",
        "entry_count": sum(1 for _ in open(dl_path, encoding="utf-8")) if dl_path.exists() else 0,
    }

    return manifest


def write_run_manifest(state: RunState, staging_dir: Path) -> Path:
    """Build and write FORGEPROOF/run.json. Returns the path."""
    manifest = build_run_manifest(state, staging_dir)
    fp_dir = staging_dir / "FORGEPROOF"
    fp_dir.mkdir(parents=True, exist_ok=True)
    out = fp_dir / "run.json"
    out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return out
