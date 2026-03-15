"""Phase 1: Parse issue and generate implementation plan via Claude."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from forgeproof.claude.prompts import (
    PARSE_PLAN_SYSTEM,
    PARSE_PLAN_USER,
    acceptance_criteria_section,
    agents_md_section,
    existing_files_section,
    priority_files_section,
)
from forgeproof.context.issue_loader import (
    extract_acceptance_criteria,
    parse_issue_context,
    parse_trigger,
)
from forgeproof.context.repo_scanner import (
    read_agents_md,
    read_files,
    read_priority_files,
    scan_repo_tree,
    select_relevant_files,
)
from forgeproof.models import Plan, PlanStep, Requirement

if TYPE_CHECKING:
    from forgeproof.orchestrator import Orchestrator

log = logging.getLogger(__name__)


def run_parse_plan(orch: "Orchestrator") -> str:
    """Execute Phase 1: parse issue context and generate a plan."""
    cfg = orch.config
    state = orch.state

    # Parse trigger and issue from GitLab env vars
    if cfg.ai_flow_context:
        state.issue = parse_issue_context(cfg.ai_flow_context)
        state.trigger = parse_trigger(cfg.ai_flow_input)
    elif not state.issue.issue_title:
        log.warning("No issue context available; using empty issue")

    # Scan repository
    repo_tree = scan_repo_tree(cfg.repo_root)
    agents_md = read_agents_md(cfg.repo_root)
    pfiles = read_priority_files(cfg.repo_root)

    # Extract acceptance criteria from issue body
    criteria = extract_acceptance_criteria(state.issue.issue_body)

    # Pre-read likely relevant files (source + test files)
    candidate_files = select_relevant_files(repo_tree)
    # Limit to a reasonable context window
    files_to_read = candidate_files[:30]
    existing = read_files(cfg.repo_root, files_to_read)

    # Build the prompt using templates
    prompt = PARSE_PLAN_USER.format(
        issue_title=state.issue.issue_title,
        issue_body=state.issue.issue_body,
        acceptance_criteria_section=acceptance_criteria_section(criteria),
        agents_md_section=agents_md_section(agents_md),
        repo_tree="\n".join(repo_tree[:200]),
        priority_files_section=priority_files_section(pfiles),
        existing_files_section=existing_files_section(existing),
    )

    # Call Claude
    assert orch.claude is not None
    response = orch.claude.ask(prompt, system=PARSE_PLAN_SYSTEM)
    orch.recorder.record("parse_plan", prompt, response, system=PARSE_PLAN_SYSTEM)

    # Parse plan from response
    plan = _parse_plan_response(response)
    state.plan = plan

    # Now read the files the plan identified as relevant (if we didn't already)
    new_files = [f for f in plan.relevant_files if f not in existing]
    if new_files:
        extra = read_files(cfg.repo_root, new_files)
        existing.update(extra)
        state.plan._repo_context = existing  # type: ignore[attr-defined]

    orch.decision_log.append(
        phase="parse_plan",
        backend="claude",
        decision_summary=(
            f"Generated plan: {len(plan.requirements)} requirements, "
            f"{len(plan.steps)} steps, {len(plan.relevant_files)} relevant files"
        ),
        artifacts_emitted=["plans/plan.json"],
    )

    return (
        f"Parsed {len(plan.requirements)} requirements, "
        f"{len(plan.steps)} implementation steps"
    )


def _parse_plan_response(response: str) -> Plan:
    """Extract Plan from Claude's JSON response."""
    text = _strip_code_fence(response)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: try to find JSON object in the response
        data = _extract_json_object(text)
        if data is None:
            log.error("Failed to parse plan JSON from Claude response: %.200s", text)
            return Plan()

    requirements = []
    for r in data.get("requirements", []):
        try:
            requirements.append(Requirement(**r))
        except Exception:
            log.warning("Skipping malformed requirement: %s", r)

    steps = []
    for s in data.get("steps", []):
        try:
            steps.append(PlanStep(**s))
        except Exception:
            log.warning("Skipping malformed step: %s", s)

    return Plan(
        requirements=requirements,
        steps=steps,
        relevant_files=data.get("relevant_files", []),
        risk_notes=data.get("risk_notes", []),
    )


def _extract_json_object(text: str) -> dict | None:
    """Try to extract a JSON object from text that may have surrounding prose."""
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _strip_code_fence(text: str) -> str:
    """Remove markdown code fences from Claude output.

    Handles ```json, ```python, and bare ``` openers.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Skip first line (```json, ```python, or bare ```)
        start = 1
        end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[start:end]).strip()
    return text
