"""Append-only, hash-chained decision log (JSONL)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_GENESIS_HASH = "0" * 64


def _canon(obj: Any) -> bytes:
    """Canonical JSON bytes for deterministic hashing."""
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DecisionLog:
    """Append-only hash-chained JSONL writer."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._seq = 0
        self._prev_hash = _GENESIS_HASH
        self._entries: list[dict[str, Any]] = []
        path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def last_hash(self) -> str:
        return self._prev_hash

    @property
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def append(
        self,
        phase: str,
        *,
        agent: str = "orchestrator",
        backend: str = "claude",
        model_id: str = "",
        temperature: float | None = None,
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
        prompt_path: str = "",
        prompt_sha256: str = "",
        output_path: str = "",
        output_sha256: str = "",
        decision_summary: str = "",
        artifacts_emitted: list[str] | None = None,
        status: str = "success",
        duration_ms: int = 0,
    ) -> dict[str, Any]:
        """Append a decision log entry and return it."""
        self._seq += 1

        entry: dict[str, Any] = {
            "seq": self._seq,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase": phase,
            "agent": agent,
            "backend": backend,
            "model_id": model_id,
            "temperature": temperature,
            "input_refs": input_refs or [],
            "output_refs": output_refs or [],
            "prompt_path": prompt_path,
            "prompt_sha256": prompt_sha256,
            "output_path": output_path,
            "output_sha256": output_sha256,
            "decision_summary": decision_summary,
            "artifacts_emitted": artifacts_emitted or [],
            "status": status,
            "duration_ms": duration_ms,
            "prev_hash": self._prev_hash,
        }

        # Compute entry_hash over all fields except entry_hash itself
        entry_hash = _sha256(_canon(entry))
        entry["entry_hash"] = entry_hash
        self._prev_hash = entry_hash

        self._entries.append(entry)

        # Append to file
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")

        log.info("Decision log #%d: %s — %s", self._seq, phase, decision_summary[:80])
        return entry

    @staticmethod
    def verify_chain(path: Path) -> tuple[bool, list[str]]:
        """Verify hash chain integrity. Returns (valid, errors)."""
        errors: list[str] = []
        prev_hash = _GENESIS_HASH

        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"Line {i}: invalid JSON")
                    continue

                stored_hash = entry.pop("entry_hash", "")
                if entry.get("prev_hash") != prev_hash:
                    errors.append(
                        f"Line {i}: prev_hash mismatch "
                        f"(expected {prev_hash[:16]}..., got {entry.get('prev_hash', '')[:16]}...)"
                    )

                computed = _sha256(_canon(entry))
                if computed != stored_hash:
                    errors.append(
                        f"Line {i}: entry_hash mismatch "
                        f"(computed {computed[:16]}..., stored {stored_hash[:16]}...)"
                    )
                prev_hash = stored_hash

        return len(errors) == 0, errors
