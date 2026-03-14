"""Shared data models for ForgeProof."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = uuid4().hex[:8]
    return f"fp_{ts}_{short}"


# ---------------------------------------------------------------------------
# Trigger / Issue context
# ---------------------------------------------------------------------------

class TriggerInfo(BaseModel):
    type: str = "mention"
    comment_id: int | None = None
    user: str = ""
    raw_input: str = ""


class IssueInfo(BaseModel):
    project_id: int = 0
    issue_iid: int = 0
    issue_title: str = ""
    issue_body: str = ""
    labels: list[str] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)


class GitInfo(BaseModel):
    base_branch: str = "main"
    base_commit: str = ""
    work_branch: str = ""
    head_commit: str = ""


# ---------------------------------------------------------------------------
# Plan / Requirements
# ---------------------------------------------------------------------------

class Requirement(BaseModel):
    id: str
    description: str
    acceptance_criteria: str = ""
    source: str = "issue"


class PlanStep(BaseModel):
    step: int
    action: str
    file_path: str
    description: str


class Plan(BaseModel):
    requirements: list[Requirement] = Field(default_factory=list)
    steps: list[PlanStep] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class FileChange(BaseModel):
    path: str
    content: str
    action: str = "create"  # create | modify | delete


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

class CommandResult(BaseModel):
    name: str
    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    required: bool = True


class EvalScorecard(BaseModel):
    deterministic_pass: bool = False
    command_results: list[CommandResult] = Field(default_factory=list)
    requirements_coverage: float = 0.0
    review_ready: bool = False
    gate_failures: list[str] = Field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Phase status
# ---------------------------------------------------------------------------

class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PhaseResult(BaseModel):
    phase: str
    status: PhaseStatus
    started_utc: str = ""
    ended_utc: str = ""
    summary: str = ""
    artifacts: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Run state (top-level)
# ---------------------------------------------------------------------------

class RunState(BaseModel):
    run_id: str = Field(default_factory=_run_id)
    created_utc: str = Field(default_factory=_utcnow)
    trigger: TriggerInfo = Field(default_factory=TriggerInfo)
    issue: IssueInfo = Field(default_factory=IssueInfo)
    git: GitInfo = Field(default_factory=GitInfo)
    plan: Plan | None = None
    file_changes: list[FileChange] = Field(default_factory=list)
    evaluation: EvalScorecard | None = None
    phases: list[PhaseResult] = Field(default_factory=list)
    pack_path: str = ""
