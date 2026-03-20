"""Tests for ForgeProof configuration loading."""

import os
from unittest.mock import patch

from forgeproof.config import GatesConfig, load_config


def test_load_config_defaults(tmp_path):
    """load_config with no YAML returns sensible defaults."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = load_config(tmp_path)

    assert cfg.repo_root == tmp_path
    assert cfg.allowed_paths == ["src/**/*.py", "tests/**/*.py"]
    assert cfg.denied_paths == [".env", "**/*.key", "**/*.pem"]
    assert len(cfg.evaluation) == 2
    assert cfg.evaluation[0].name == "tests"
    assert cfg.evaluation[1].name == "lint"
    assert cfg.gates.requirements_coverage_min == 80.0
    assert cfg.signing.key_path == "devkey.ed25519"


def test_load_config_from_yaml(tmp_path):
    """load_config reads .forgeproof.yml and overrides defaults."""
    yml = tmp_path / ".forgeproof.yml"
    yml.write_text(
        "allowed_paths:\n"
        '  - "lib/**/*.py"\n'
        "gates:\n"
        "  requirements_coverage_min: 90\n",
        encoding="utf-8",
    )
    with patch.dict(os.environ, {}, clear=True):
        cfg = load_config(tmp_path)

    assert cfg.allowed_paths == ["lib/**/*.py"]
    assert cfg.gates.requirements_coverage_min == 90.0


def test_load_config_yaml_evaluation(tmp_path):
    """load_config reads evaluation commands from YAML."""
    yml = tmp_path / ".forgeproof.yml"
    yml.write_text(
        "evaluation:\n"
        "  commands:\n"
        '    - name: mytest\n'
        '      run: "echo ok"\n'
        '      required: false\n',
        encoding="utf-8",
    )
    with patch.dict(os.environ, {}, clear=True):
        cfg = load_config(tmp_path)

    assert len(cfg.evaluation) == 1
    assert cfg.evaluation[0].name == "mytest"
    assert cfg.evaluation[0].required is False


def test_gitlab_token_precedence(tmp_path):
    """GITLAB_TOKEN takes precedence over CI_JOB_TOKEN."""
    env = {"GITLAB_TOKEN": "glpat-abc", "CI_JOB_TOKEN": "job-xyz"}
    with patch.dict(os.environ, env, clear=True):
        cfg = load_config(tmp_path)
    assert cfg.gitlab_token == "glpat-abc"


def test_ci_job_token_fallback(tmp_path):
    """CI_JOB_TOKEN used when GITLAB_TOKEN is not set."""
    env = {"CI_JOB_TOKEN": "job-xyz"}
    with patch.dict(os.environ, env, clear=True):
        cfg = load_config(tmp_path)
    assert cfg.gitlab_token == "job-xyz"


def test_project_id_int_conversion(tmp_path):
    """CI_PROJECT_ID string is converted to int."""
    env = {"CI_PROJECT_ID": "12345"}
    with patch.dict(os.environ, env, clear=True):
        cfg = load_config(tmp_path)
    assert cfg.project_id == 12345
    assert isinstance(cfg.project_id, int)


def test_anthropic_api_key(tmp_path):
    """ANTHROPIC_API_KEY is loaded from environment."""
    env = {"ANTHROPIC_API_KEY": "sk-test-key"}
    with patch.dict(os.environ, env, clear=True):
        cfg = load_config(tmp_path)
    assert cfg.anthropic_api_key == "sk-test-key"


def test_gates_config_defaults():
    g = GatesConfig()
    assert g.all_required_commands_pass is True
    assert g.requirements_coverage_min == 80.0


def test_no_yaml_file(tmp_path):
    """No crash when .forgeproof.yml does not exist."""
    with patch.dict(os.environ, {}, clear=True):
        cfg = load_config(tmp_path)
    assert cfg.repo_root == tmp_path
