"""Configuration loader: env vars + .forgeproof.yml."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class EvalCommand(BaseModel):
    name: str
    run: str
    required: bool = True


class GatesConfig(BaseModel):
    all_required_commands_pass: bool = True
    requirements_coverage_min: float = 80.0


class SigningConfig(BaseModel):
    key_path: str = "devkey.ed25519"
    policy_profile: str = "P2"


class ForgeProofConfig(BaseModel):
    allowed_paths: list[str] = Field(default_factory=lambda: ["src/**/*.py", "tests/**/*.py"])
    denied_paths: list[str] = Field(default_factory=lambda: [".env", "**/*.key", "**/*.pem"])
    evaluation: list[EvalCommand] = Field(default_factory=lambda: [
        EvalCommand(name="tests", run="python -m pytest -q", required=True),
        EvalCommand(name="lint", run="python -m ruff check .", required=True),
    ])
    gates: GatesConfig = Field(default_factory=GatesConfig)
    signing: SigningConfig = Field(default_factory=SigningConfig)

    # Runtime env (not from YAML)
    repo_root: Path = Field(default_factory=lambda: Path.cwd())
    anthropic_base_url: str = ""
    anthropic_auth_token: str = ""
    anthropic_custom_headers: str = ""
    anthropic_api_key: str = ""  # local dev fallback
    gitlab_base_url: str = ""
    gitlab_token: str = ""
    ai_flow_context: str = ""
    ai_flow_input: str = ""
    project_id: int = 0


def load_config(repo_root: Path | None = None) -> ForgeProofConfig:
    root = repo_root or Path.cwd()
    cfg = ForgeProofConfig(repo_root=root)

    # Load YAML config if present
    yml_path = root / ".forgeproof.yml"
    if yml_path.exists():
        raw = yaml.safe_load(yml_path.read_text(encoding="utf-8")) or {}
        if "allowed_paths" in raw:
            cfg.allowed_paths = raw["allowed_paths"]
        if "denied_paths" in raw:
            cfg.denied_paths = raw["denied_paths"]
        if "evaluation" in raw and "commands" in raw["evaluation"]:
            cfg.evaluation = [EvalCommand(**c) for c in raw["evaluation"]["commands"]]
        if "gates" in raw:
            cfg.gates = GatesConfig(**raw["gates"])
        if "signing" in raw:
            cfg.signing = SigningConfig(**raw["signing"])

    # Load env vars (GitLab Duo Agent Platform injects these)
    cfg.anthropic_base_url = os.environ.get(
        "ANTHROPIC_BASE_URL",
        "https://cloud.gitlab.com/ai/v1/proxy/anthropic",
    )
    cfg.anthropic_auth_token = os.environ.get("AI_FLOW_AI_GATEWAY_TOKEN", "")
    cfg.anthropic_custom_headers = os.environ.get("AI_FLOW_AI_GATEWAY_HEADERS", "")
    cfg.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")  # local dev
    cfg.gitlab_base_url = os.environ.get("GITLAB_BASE_URL", "https://gitlab.com")
    cfg.gitlab_token = os.environ.get("CI_JOB_TOKEN", os.environ.get("GITLAB_TOKEN", ""))
    cfg.ai_flow_context = os.environ.get("AI_FLOW_CONTEXT", "")
    cfg.ai_flow_input = os.environ.get("AI_FLOW_INPUT", "")
    cfg.project_id = int(os.environ.get("CI_PROJECT_ID", "0"))

    return cfg
