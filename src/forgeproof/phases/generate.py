"""Phase 2: Generate code and test changes via Claude."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from forgeproof.claude.prompts import (
    GENERATE_CODE_SYSTEM,
    GENERATE_CODE_USER,
    GENERATE_TESTS_SYSTEM,
    GENERATE_TESTS_USER,
    code_changes_section,
    existing_files_section,
)
from forgeproof.context.repo_scanner import read_files
from forgeproof.models import FileChange

if TYPE_CHECKING:
    from forgeproof.orchestrator import Orchestrator

log = logging.getLogger(__name__)


def run_generate(orch: "Orchestrator") -> str:
    """Execute Phase 2: generate code files, then test files."""
    state = orch.state
    cfg = orch.config

    if not state.plan or not state.plan.steps:
        return "SKIPPED: No plan to implement"

    assert orch.claude is not None

    # Read existing files referenced in the plan
    existing = read_files(cfg.repo_root, state.plan.relevant_files)

    # Also read files targeted for modification
    modify_paths = [s.file_path for s in state.plan.steps if s.action == "modify"]
    existing.update(read_files(cfg.repo_root, modify_paths))

    # ---- Step 1: Generate implementation code ----
    code_prompt = GENERATE_CODE_USER.format(
        issue_title=state.issue.issue_title,
        issue_body=state.issue.issue_body,
        plan_json=json.dumps(state.plan.model_dump(), indent=2),
        existing_files_section=existing_files_section(existing),
    )

    code_response = orch.claude.ask(code_prompt, system=GENERATE_CODE_SYSTEM)
    orch.recorder.record("generate_code", code_prompt, code_response, system=GENERATE_CODE_SYSTEM)

    code_changes = _parse_changes(code_response)

    orch.decision_log.append(
        phase="generate_code",
        backend="claude",
        decision_summary=f"Generated {len(code_changes)} code files",
        artifacts_emitted=[c.path for c in code_changes],
    )

    # ---- Step 2: Generate tests ----
    # Collect existing test files for context
    test_files = {p: c for p, c in existing.items() if "test" in p.lower()}

    test_prompt = GENERATE_TESTS_USER.format(
        requirements_json=json.dumps(
            [r.model_dump() for r in state.plan.requirements], indent=2
        ),
        code_changes_section=code_changes_section(code_changes),
        existing_test_section=existing_files_section(test_files) if test_files else "(no existing tests)",
    )

    test_response = orch.claude.ask(test_prompt, system=GENERATE_TESTS_SYSTEM)
    orch.recorder.record("generate_tests", test_prompt, test_response, system=GENERATE_TESTS_SYSTEM)

    test_changes = _parse_changes(test_response)

    orch.decision_log.append(
        phase="generate_tests",
        backend="claude",
        decision_summary=f"Generated {len(test_changes)} test files",
        artifacts_emitted=[c.path for c in test_changes],
    )

    # Merge all changes, deduplicating by path (test gen wins over code gen for test files)
    seen: dict[str, FileChange] = {}
    for c in code_changes:
        seen[c.path] = c
    for c in test_changes:
        seen[c.path] = c  # test generation overrides code gen for same path
    all_changes = list(seen.values())
    state.file_changes = all_changes

    code_paths = [c.path for c in code_changes]
    test_paths = [c.path for c in test_changes]
    return (
        f"Generated {len(code_changes)} code files ({', '.join(code_paths)}), "
        f"{len(test_changes)} test files ({', '.join(test_paths)})"
    )


def _parse_changes(response: str) -> list[FileChange]:
    """Extract FileChange list from Claude's JSON response."""
    text = _strip_code_fence(response)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to find JSON object in the response
        data = _extract_json_object(text)
        if data is None:
            log.error("Failed to parse generation JSON: %.200s", text)
            return []

    changes = []
    for c in data.get("changes", []):
        if not c.get("path") or not c.get("content"):
            log.warning("Skipping change with missing path or content")
            continue
        changes.append(FileChange(
            path=c["path"],
            content=c["content"],
            action=c.get("action", "create"),
        ))
    return changes


def _extract_json_object(text: str) -> dict | None:
    """Try to extract a JSON object from text that may have surrounding prose."""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()
    return text
