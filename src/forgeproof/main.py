"""ForgeProof CLI entrypoint."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import typer

from forgeproof.config import load_config
from forgeproof.orchestrator import Orchestrator

app = typer.Typer(name="forgeproof", help="AI agent: issue → review-ready MR with signed provenance")


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@app.command()
def run(
    repo: Path = typer.Option(Path.cwd(), help="Repository root"),
    issue_file: Path | None = typer.Option(None, help="Local issue JSON/MD file (dev mode)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_json: bool = typer.Option(False, "--json", help="Output run state as JSON"),
) -> None:
    """Run the ForgeProof pipeline."""
    _setup_logging(verbose)
    log = logging.getLogger("forgeproof")

    config = load_config(repo)
    orch = Orchestrator(config)

    # Load issue from file in local dev mode
    if issue_file:
        text = issue_file.read_text(encoding="utf-8")
        if issue_file.suffix == ".json":
            from forgeproof.context.issue_loader import load_issue_from_file
            orch.state.issue = load_issue_from_file(str(issue_file))
        else:
            from forgeproof.context.issue_loader import load_issue_from_markdown
            orch.state.issue = load_issue_from_markdown(text)

    state = orch.run()

    if output_json:
        print(json.dumps(state.model_dump(), indent=2, default=str))
    else:
        _print_summary(state)

    # Exit with non-zero if not review-ready
    if state.evaluation and not state.evaluation.review_ready:
        raise typer.Exit(code=1)


@app.command()
def verify(
    pack: Path = typer.Argument(..., help="Path to .rpack file or unpacked directory"),
    pubkey: Path | None = typer.Option(None, help="Public key for signature verification"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Verify a ForgeProof .rpack provenance bundle."""
    _setup_logging(verbose)
    log = logging.getLogger("forgeproof")

    # Bootstrap RPB imports
    rpb_root = Path(__file__).resolve().parents[2] / "Replication-Pack"
    if str(rpb_root) not in sys.path:
        sys.path.insert(0, str(rpb_root))

    from internal.rpb.verify_signatures import verify_pack_directory  # type: ignore[import-untyped]
    from internal.rpb.pack_reader import extract_rpack  # type: ignore[import-untyped]

    # Extract if .rpack archive
    target = pack
    if pack.is_file() and pack.suffix == ".rpack":
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="forgeproof_verify_"))
        extract_rpack(str(pack), str(tmp))
        target = tmp

    # Run RPB verification
    pubkey_paths = [str(pubkey)] if pubkey else []
    result = verify_pack_directory(str(target), pubkey_paths)

    # Also verify decision log hash chain
    dl_path = target / "FORGEPROOF" / "decision_log.jsonl"
    if dl_path.exists():
        from forgeproof.provenance.decision_log import DecisionLog
        chain_ok, chain_errors = DecisionLog.verify_chain(dl_path)
        if chain_ok:
            log.info("Decision log hash chain: VALID")
        else:
            log.error("Decision log hash chain: INVALID")
            for err in chain_errors:
                log.error("  %s", err)

    # Print ForgeProof run manifest if present
    run_json = target / "FORGEPROOF" / "run.json"
    if run_json.exists():
        data = json.loads(run_json.read_text(encoding="utf-8"))
        log.info("ForgeProof run: %s", data.get("run_id", "unknown"))
        if "evaluation" in data:
            eval_data = data["evaluation"]
            log.info("  Review-ready: %s", eval_data.get("review_ready", "unknown"))
            log.info("  Coverage: %s%%", eval_data.get("requirements_coverage", "?"))

    if result.verified:
        typer.echo("VERIFIED: Pack signatures and hashes are valid.")
        raise typer.Exit(code=0)
    else:
        typer.echo("FAILED: Verification failed.")
        for check in result.failed_checks:
            typer.echo(f"  - {check}")
        raise typer.Exit(code=2)


def _print_summary(state) -> None:
    typer.echo(f"\n{'='*60}")
    typer.echo(f"ForgeProof Run: {state.run_id}")
    typer.echo(f"{'='*60}")

    for phase in state.phases:
        icon = "PASS" if phase.status.value == "passed" else "FAIL"
        typer.echo(f"  [{icon}] {phase.phase}: {phase.summary}")

    if state.evaluation:
        ev = state.evaluation
        typer.echo(f"\nEvaluation:")
        typer.echo(f"  Review-ready: {ev.review_ready}")
        typer.echo(f"  Coverage: {ev.requirements_coverage:.0f}%")
        if ev.gate_failures:
            typer.echo(f"  Gate failures:")
            for f in ev.gate_failures:
                typer.echo(f"    - {f}")

    if state.pack_path:
        typer.echo(f"\nPack: {state.pack_path}")

    typer.echo("")


if __name__ == "__main__":
    app()
