"""Record all Claude prompts and responses for provenance capture."""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


class Recorder:
    """Saves every prompt/response pair to numbered files in a directory."""

    def __init__(self, output_dir: Path) -> None:
        self._dir = output_dir
        self._prompts_dir = output_dir / "prompts"
        self._outputs_dir = output_dir / "outputs"
        self._prompts_dir.mkdir(parents=True, exist_ok=True)
        self._outputs_dir.mkdir(parents=True, exist_ok=True)
        self._seq = 0

    @property
    def sequence(self) -> int:
        return self._seq

    def record(
        self,
        phase: str,
        prompt: str,
        response: str,
        *,
        system: str = "",
        model: str = "",
        metadata: dict | None = None,
    ) -> tuple[str, str]:
        """Save a prompt/response pair and return (prompt_path, output_path)."""
        self._seq += 1
        prefix = f"{self._seq:03d}_{phase}"

        prompt_file = self._prompts_dir / f"{prefix}.txt"
        output_file = self._outputs_dir / f"{prefix}.json"

        prompt_file.write_text(prompt, encoding="utf-8")

        record = {
            "seq": self._seq,
            "phase": phase,
            "model": model,
            "system_prompt_length": len(system),
            "prompt_length": len(prompt),
            "response_length": len(response),
            "response": response,
        }
        if metadata:
            record["metadata"] = metadata

        output_file.write_text(
            json.dumps(record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        log.info("Recorded prompt/response #%d for phase '%s'", self._seq, phase)
        return str(prompt_file.name), str(output_file.name)
