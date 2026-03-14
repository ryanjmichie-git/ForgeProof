#!/usr/bin/env python3
"""Local development runner — simulates ForgeProof without GitLab.

Usage:
    python scripts/local_run.py --repo demo/seed-repo --issue demo/sample-issue.md
    python scripts/local_run.py --repo demo/seed-repo --issue demo/sample-issue.md --json
    python scripts/local_run.py --repo demo/seed-repo --issue demo/sample-issue.md -v

Requires ANTHROPIC_API_KEY environment variable.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure ForgeProof is importable
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / "src"))

from forgeproof.config import load_config
from forgeproof.context.issue_loader import load_issue_from_markdown
from forgeproof.orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="ForgeProof local dev runner")
    parser.add_argument("--repo", type=Path, required=True, help="Path to target repo")
    parser.add_argument("--issue", type=Path, required=True, help="Path to issue markdown file")
    parser.add_argument("--json", action="store_true", help="Output run state as JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("forgeproof")

    repo = args.repo.resolve()
    if not repo.is_dir():
        log.error("Repo path does not exist: %s", repo)
        sys.exit(1)

    issue_text = args.issue.read_text(encoding="utf-8")
    issue = load_issue_from_markdown(issue_text)

    log.info("Starting ForgeProof local run")
    log.info("  Repo: %s", repo)
    log.info("  Issue: %s", issue.issue_title)

    config = load_config(repo)
    orch = Orchestrator(config)
    orch.state.issue = issue

    state = orch.run()

    if args.json:
        print(json.dumps(state.model_dump(), indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"ForgeProof Run: {state.run_id}")
        print(f"{'='*60}")

        for phase in state.phases:
            icon = "PASS" if phase.status.value == "passed" else "FAIL"
            print(f"  [{icon}] {phase.phase}: {phase.summary}")

        if state.evaluation:
            ev = state.evaluation
            print(f"\nEvaluation:")
            print(f"  Review-ready: {ev.review_ready}")
            print(f"  Coverage: {ev.requirements_coverage:.0f}%")
            if ev.gate_failures:
                print(f"  Gate failures:")
                for f in ev.gate_failures:
                    print(f"    - {f}")

        if state.pack_path:
            print(f"\nPack: {state.pack_path}")

        if state.file_changes:
            print(f"\nGenerated files:")
            for fc in state.file_changes:
                print(f"  [{fc.action}] {fc.path} ({len(fc.content)} chars)")

        print()

    sys.exit(0 if state.evaluation and state.evaluation.review_ready else 1)


if __name__ == "__main__":
    main()
