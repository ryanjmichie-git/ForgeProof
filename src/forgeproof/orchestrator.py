"""ForgeProof orchestrator: 4-phase state machine.

Phase 1: PARSE & PLAN — read issue, scan repo, generate plan via Claude
Phase 2: GENERATE    — generate code + tests via Claude
Phase 3: EVALUATE    — run pytest/ruff, score requirements coverage
Phase 4: PACKAGE     — build staging dir, sign, create .rpack
"""

from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from forgeproof.claude.client import ClaudeClient
from forgeproof.claude.recorder import Recorder
from forgeproof.config import ForgeProofConfig
from forgeproof.models import (
    EvalScorecard,
    PhaseResult,
    PhaseStatus,
    RunState,
    _utcnow,
)
from forgeproof.provenance.decision_log import DecisionLog
from forgeproof.provenance.packer import build_staging_directory, sign_and_pack
from forgeproof.provenance.run_manifest import write_run_manifest

log = logging.getLogger(__name__)


class Orchestrator:
    """Runs the 4-phase ForgeProof pipeline."""

    def __init__(self, config: ForgeProofConfig) -> None:
        self.config = config
        self.state = RunState()
        self.work_dir = Path(tempfile.mkdtemp(prefix="forgeproof_run_"))

        # Initialize recorder and decision log
        self.recorder = Recorder(self.work_dir)
        self.decision_log = DecisionLog(self.work_dir / "decision_log.jsonl")

        # Claude client (may raise if no credentials)
        self.claude: ClaudeClient | None = None

    def run(self) -> RunState:
        """Execute all four phases and return the final run state."""
        log.info("=== ForgeProof run %s starting ===", self.state.run_id)

        try:
            self.claude = ClaudeClient(self.config)
        except RuntimeError as exc:
            log.error("Cannot initialize Claude client: %s", exc)
            self.state.phases.append(PhaseResult(
                phase="init",
                status=PhaseStatus.FAILED,
                summary=str(exc),
            ))
            return self.state

        phases = [
            ("parse_plan", self._phase_parse_plan),
            ("generate", self._phase_generate),
            ("evaluate", self._phase_evaluate),
            ("package", self._phase_package),
        ]

        for name, fn in phases:
            result = self._run_phase(name, fn)
            self.state.phases.append(result)
            if result.status == PhaseStatus.FAILED:
                log.warning("Phase '%s' failed: %s", name, result.summary)
                # Continue to packaging even on failure (create draft MR)
                if name not in ("package",):
                    continue
                break

        log.info("=== ForgeProof run %s complete ===", self.state.run_id)
        return self.state

    def _run_phase(self, name: str, fn) -> PhaseResult:
        started = _utcnow()
        t0 = time.monotonic()
        try:
            summary = fn()
            elapsed = int((time.monotonic() - t0) * 1000)
            self.decision_log.append(
                phase=name,
                decision_summary=summary or f"Phase {name} completed",
                status="success",
                duration_ms=elapsed,
            )
            return PhaseResult(
                phase=name,
                status=PhaseStatus.PASSED,
                started_utc=started,
                ended_utc=_utcnow(),
                summary=summary or "",
            )
        except Exception as exc:
            elapsed = int((time.monotonic() - t0) * 1000)
            log.exception("Phase '%s' raised an exception", name)
            self.decision_log.append(
                phase=name,
                decision_summary=f"FAILED: {exc}",
                status="failure",
                duration_ms=elapsed,
            )
            return PhaseResult(
                phase=name,
                status=PhaseStatus.FAILED,
                started_utc=started,
                ended_utc=_utcnow(),
                summary=str(exc),
            )

    # ------------------------------------------------------------------
    # Phase 1: Parse & Plan
    # ------------------------------------------------------------------

    def _phase_parse_plan(self) -> str:
        from forgeproof.phases.parse_plan import run_parse_plan

        return run_parse_plan(self)

    # ------------------------------------------------------------------
    # Phase 2: Generate
    # ------------------------------------------------------------------

    def _phase_generate(self) -> str:
        from forgeproof.phases.generate import run_generate

        return run_generate(self)

    # ------------------------------------------------------------------
    # Phase 3: Evaluate
    # ------------------------------------------------------------------

    def _phase_evaluate(self) -> str:
        from forgeproof.phases.evaluate import run_evaluate

        return run_evaluate(self)

    # ------------------------------------------------------------------
    # Phase 4: Package & Ship
    # ------------------------------------------------------------------

    def _phase_package(self) -> str:
        log.info("Phase 4: Building provenance pack")

        # Build staging directory
        staging_dir = build_staging_directory(
            self.state,
            prompts_dir=self.work_dir / "prompts",
            outputs_dir=self.work_dir / "outputs",
            decision_log_path=self.work_dir / "decision_log.jsonl",
            work_dir=self.work_dir / "staging",
        )

        # Write ForgeProof run manifest
        write_run_manifest(self.state, staging_dir)

        # Sign and pack
        key_path = self.config.repo_root / self.config.signing.key_path
        if not key_path.exists():
            # Try RPB's dev key as fallback
            rpb_key = Path(__file__).resolve().parents[1] / "Replication-Pack" / "devkey.ed25519"
            if rpb_key.exists():
                key_path = rpb_key
            else:
                return "SKIPPED: No signing key found"

        output_path = self.work_dir / f"{self.state.run_id}.rpack"
        sign_and_pack(staging_dir, key_path, output_path)
        self.state.pack_path = str(output_path)

        return f"Pack created at {output_path} ({output_path.stat().st_size} bytes)"
