"""Parse AI_FLOW_CONTEXT and AI_FLOW_INPUT into structured issue data."""

from __future__ import annotations

import json
import logging
import re

from forgeproof.models import IssueInfo, TriggerInfo

log = logging.getLogger(__name__)


def parse_trigger(ai_flow_input: str) -> TriggerInfo:
    """Extract trigger metadata from AI_FLOW_INPUT."""
    return TriggerInfo(
        type="mention",
        raw_input=ai_flow_input.strip(),
    )


def parse_issue_context(ai_flow_context: str) -> IssueInfo:
    """Parse AI_FLOW_CONTEXT JSON into IssueInfo.

    GitLab injects structured context containing the issue/MR data.
    The exact schema may vary; we extract what we can and fall back gracefully.
    """
    if not ai_flow_context:
        log.warning("AI_FLOW_CONTEXT is empty; returning blank IssueInfo")
        return IssueInfo()

    try:
        ctx = json.loads(ai_flow_context)
    except json.JSONDecodeError:
        log.error("Failed to parse AI_FLOW_CONTEXT as JSON")
        return IssueInfo()

    # GitLab context structure may nest under various keys
    issue_data = ctx if isinstance(ctx, dict) else {}

    # Try common context shapes
    if "issue" in issue_data:
        issue_data = issue_data["issue"]
    elif "parent_object" in issue_data:
        issue_data = issue_data["parent_object"]

    return IssueInfo(
        project_id=_int(issue_data.get("project_id", 0)),
        issue_iid=_int(issue_data.get("iid", 0)),
        issue_title=issue_data.get("title", ""),
        issue_body=issue_data.get("description", ""),
        labels=issue_data.get("labels", []),
        comments=_extract_comments(issue_data),
    )


def load_issue_from_file(path: str) -> IssueInfo:
    """Load issue from a local JSON file (for local dev/testing)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return IssueInfo(**data)


def load_issue_from_markdown(text: str) -> IssueInfo:
    """Parse a markdown issue body into IssueInfo (for local dev)."""
    title = ""
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0].lstrip("# ").strip()

    return IssueInfo(
        issue_title=title,
        issue_body=text,
    )


def extract_acceptance_criteria(body: str) -> list[str]:
    """Pull acceptance criteria from issue body markdown."""
    criteria: list[str] = []
    in_section = False
    for line in body.splitlines():
        lower = line.lower().strip()
        if "acceptance criteria" in lower or "requirements" in lower:
            in_section = True
            continue
        if in_section:
            if line.startswith("#"):
                break
            item = re.sub(r"^[\s\-\*\[\]x]+", "", line).strip()
            if item:
                criteria.append(item)
    return criteria


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _int(v: object) -> int:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _extract_comments(data: dict) -> list[str]:
    notes = data.get("notes", data.get("comments", []))
    if isinstance(notes, list):
        return [n.get("body", str(n)) if isinstance(n, dict) else str(n) for n in notes]
    return []
