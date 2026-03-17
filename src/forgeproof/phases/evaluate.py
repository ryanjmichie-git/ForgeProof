"""Phase 3: Run evaluation commands and score requirements coverage."""

from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

from forgeproof.claude.prompts import (
    EVAL_COVERAGE_SYSTEM,
    EVAL_COVERAGE_USER,
    code_changes_section,
    test_results_section,
)
from forgeproof.models import CommandResult, EvalScorecard

if TYPE_CHECKING:
    from forgeproof.orchestrator import Orchestrator

log = logging.getLogger(__name__)


def run_evaluate(orch: "Orchestrator") -> str:
    """Execute Phase 3: write generated files, run checks, score coverage."""
    state = orch.state
    cfg = orch.config

    # Write generated files to a temp workspace so we can run tests against them
    workspace = Path(tempfile.mkdtemp(prefix="forgeproof_eval_"))
    _write_workspace(orch, workspace)

    results: list[CommandResult] = []
    gate_failures: list[str] = []

    # Install project dependencies in the workspace if pyproject.toml exists
    _install_deps(workspace)

    # Run deterministic evaluation commands in the workspace
    for cmd_cfg in cfg.evaluation:
        cr = _run_command(cmd_cfg.name, cmd_cfg.run, workspace)
        results.append(cr)
        if cmd_cfg.required and cr.exit_code != 0:
            gate_failures.append(f"{cmd_cfg.name} failed (exit {cr.exit_code})")
            log.warning("Gate failure: %s (exit %d)", cmd_cfg.name, cr.exit_code)

    # Score requirements coverage via Claude
    coverage = 0.0
    if state.plan and state.plan.requirements and orch.claude:
        coverage = _score_coverage(orch, results)

    # Determine review-readiness
    all_required_pass = len(gate_failures) == 0
    coverage_ok = coverage >= cfg.gates.requirements_coverage_min
    review_ready = all_required_pass and coverage_ok

    if not coverage_ok:
        gate_failures.append(
            f"Requirements coverage {coverage:.0f}% < {cfg.gates.requirements_coverage_min:.0f}%"
        )

    state.evaluation = EvalScorecard(
        deterministic_pass=all_required_pass,
        command_results=results,
        requirements_coverage=coverage,
        review_ready=review_ready,
        gate_failures=gate_failures,
    )

    orch.decision_log.append(
        phase="evaluate",
        decision_summary=(
            f"{'REVIEW-READY' if review_ready else 'NOT READY'}: "
            f"commands={'pass' if all_required_pass else 'fail'}, "
            f"coverage={coverage:.0f}%, "
            f"gate_failures={len(gate_failures)}"
        ),
        status="success" if review_ready else "gate_failure",
    )

    status = "REVIEW-READY" if review_ready else "NOT READY"
    return f"{status} (coverage={coverage:.0f}%, gates={len(gate_failures)} failures)"


def _write_workspace(orch: "Orchestrator", workspace: Path) -> None:
    """Write generated files into the eval workspace, overlaid on repo context."""
    import shutil

    cfg = orch.config

    # Copy the target repo as the base (if it's reasonable size)
    src_dir = cfg.repo_root / "src"
    tests_dir = cfg.repo_root / "tests"
    if src_dir.is_dir():
        shutil.copytree(src_dir, workspace / "src", dirs_exist_ok=True)
    if tests_dir.is_dir():
        shutil.copytree(tests_dir, workspace / "tests", dirs_exist_ok=True)

    # Copy config files needed for evaluation
    for name in ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "ruff.toml"):
        src = cfg.repo_root / name
        if src.is_file():
            shutil.copy2(src, workspace / name)

    # Overlay generated files
    for fc in orch.state.file_changes:
        dest = workspace / fc.path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(fc.content, encoding="utf-8")


def _install_deps(workspace: Path) -> None:
    """Install project dependencies in the eval workspace if possible."""
    pyproject = workspace / "pyproject.toml"
    requirements = workspace / "requirements.txt"

    if pyproject.exists():
        cmd = "pip install -q -e '.[dev]' 2>/dev/null || pip install -q -e . 2>/dev/null || true"
    elif requirements.exists():
        cmd = "pip install -q -r requirements.txt 2>/dev/null || true"
    else:
        return

    log.info("Installing project dependencies in eval workspace")
    try:
        subprocess.run(cmd, shell=True, cwd=str(workspace), capture_output=True, timeout=120)
    except Exception:
        log.warning("Dependency install failed; continuing without", exc_info=True)


def _run_command(name: str, command: str, cwd: Path) -> CommandResult:
    log.info("Running: %s → %s (cwd=%s)", name, command, cwd)
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = int((time.monotonic() - t0) * 1000)
        log.info("  %s exit=%d (%.1fs)", name, proc.returncode, elapsed / 1000)
        return CommandResult(
            name=name,
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout[-5000:],  # cap output for pack size
            stderr=proc.stderr[-3000:],
            duration_ms=elapsed,
        )
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - t0) * 1000)
        return CommandResult(
            name=name, command=command, exit_code=-1,
            stderr="Command timed out after 120s", duration_ms=elapsed,
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        return CommandResult(
            name=name, command=command, exit_code=-1,
            stderr=str(exc), duration_ms=elapsed,
        )


def _score_coverage(orch: "Orchestrator", cmd_results: list[CommandResult]) -> float:
    """Use Claude to score requirements coverage."""
    state = orch.state
    assert orch.claude is not None
    assert state.plan is not None

    # Separate code and test changes
    code_changes = [c for c in state.file_changes if "test" not in c.path.lower()]
    test_changes = [c for c in state.file_changes if "test" in c.path.lower()]

    prompt = EVAL_COVERAGE_USER.format(
        requirements_json=json.dumps(
            [r.model_dump() for r in state.plan.requirements], indent=2
        ),
        code_changes_section=code_changes_section(code_changes),
        test_changes_section=code_changes_section(test_changes),
        test_results_section=test_results_section(cmd_results),
    )

    try:
        data = orch.claude.ask_json(prompt, system=EVAL_COVERAGE_SYSTEM)
        orch.recorder.record(
            "evaluate_coverage", prompt, json.dumps(data),
            system=EVAL_COVERAGE_SYSTEM,
        )
        return float(data.get("coverage_pct", 0))
    except Exception:
        log.warning("Could not parse coverage score; defaulting to 0", exc_info=True)
        return 0.0
