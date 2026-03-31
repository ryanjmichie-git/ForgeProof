# tests/test_skill_config.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib"))

def test_defaults_when_no_config():
    from config import load_config
    cfg = load_config(Path("/nonexistent/.forgeproof.toml"))
    assert "src/**/*" in cfg["paths"]["allowed"]
    assert ".env" in cfg["paths"]["denied"]
    assert cfg["signing"]["ephemeral"] is True

def test_load_toml_config(tmp_path):
    from config import load_config
    toml_file = tmp_path / ".forgeproof.toml"
    toml_file.write_text('''
[paths]
allowed = ["app/**/*.py"]
denied = [".secret"]

[signing]
ephemeral = false
key_path = "my.key"
''')
    cfg = load_config(toml_file)
    assert cfg["paths"]["allowed"] == ["app/**/*.py"]
    assert cfg["paths"]["denied"] == [".secret"]
    assert cfg["signing"]["ephemeral"] is False
    assert cfg["signing"]["key_path"] == "my.key"

def test_partial_config_merges_defaults(tmp_path):
    from config import load_config
    toml_file = tmp_path / ".forgeproof.toml"
    toml_file.write_text('[signing]\nephemeral = true\n')
    cfg = load_config(toml_file)
    assert "src/**/*" in cfg["paths"]["allowed"]
    assert cfg["signing"]["ephemeral"] is True
