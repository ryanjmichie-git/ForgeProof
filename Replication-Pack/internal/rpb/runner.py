from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CommandRunResult:
    evidence_id: str
    command: str
    exit_code: int
    stdout_path: str
    stderr_path: str
    started_utc: str
    ended_utc: str

    def to_manifest_evidence(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "type": "tests",
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "outputs": [],
            "started_utc": self.started_utc,
            "ended_utc": self.ended_utc,
        }


class EvidenceRunError(RuntimeError):
    """Raised when one or more test commands fail during evidence capture."""

    def __init__(self, message: str, results: list[CommandRunResult]) -> None:
        super().__init__(message)
        self.results = results


def _run_single_command(
    *,
    command: str,
    index: int,
    work_dir: Path,
    evidence_dir: Path,
    shell: bool,
) -> CommandRunResult:
    evidence_id = f"EVID-TESTS-{index:03d}"
    file_prefix = f"test-{index:03d}"
    stdout_rel = f"EVIDENCE/TESTS/{file_prefix}_stdout.txt"
    stderr_rel = f"EVIDENCE/TESTS/{file_prefix}_stderr.txt"
    stdout_file = evidence_dir / f"{file_prefix}_stdout.txt"
    stderr_file = evidence_dir / f"{file_prefix}_stderr.txt"

    started_utc = _utc_now()
    completed = subprocess.run(
        command,
        cwd=str(work_dir),
        shell=shell,
        capture_output=True,
        text=True,
        check=False,
    )
    ended_utc = _utc_now()

    stdout_file.write_text(completed.stdout or "", encoding="utf-8")
    stderr_file.write_text(completed.stderr or "", encoding="utf-8")

    return CommandRunResult(
        evidence_id=evidence_id,
        command=command,
        exit_code=completed.returncode,
        stdout_path=stdout_rel,
        stderr_path=stderr_rel,
        started_utc=started_utc,
        ended_utc=ended_utc,
    )


def run_test_commands(
    commands: list[str],
    *,
    work_dir: str | Path,
    evidence_dir: str | Path,
    stop_on_failure: bool = True,
    shell: bool = True,
) -> list[CommandRunResult]:
    """Execute test commands and write stdout/stderr evidence files."""

    if not commands:
        return []

    work_path = Path(work_dir)
    evidence_path = Path(evidence_dir)
    evidence_path.mkdir(parents=True, exist_ok=True)

    results: list[CommandRunResult] = []
    failures: list[CommandRunResult] = []
    for index, command in enumerate(commands, start=1):
        result = _run_single_command(
            command=command,
            index=index,
            work_dir=work_path,
            evidence_dir=evidence_path,
            shell=shell,
        )
        results.append(result)
        if result.exit_code != 0:
            failures.append(result)
            if stop_on_failure:
                break

    if failures:
        failed_ids = ",".join(item.evidence_id for item in failures)
        first = failures[0]
        raise EvidenceRunError(
            f"tests_failed:{failed_ids}; failing_command={first.command}; exit_code={first.exit_code}",
            results,
        )
    return results
