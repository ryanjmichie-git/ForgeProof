# tests/test_skill_decision_log.py
import json
import subprocess
import sys
from pathlib import Path

LIB_DIR = str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib")
sys.path.insert(0, LIB_DIR)

def test_append_first_entry(tmp_path):
    log_path = tmp_path / "log.jsonl"
    result = subprocess.run(
        [sys.executable, f"{LIB_DIR}/decision_log.py", "append",
         "--log", str(log_path),
         "--phase", "parse",
         "--action", "planned",
         "--detail", "3 requirements extracted"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    entries = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
    assert len(entries) == 1
    assert entries[0]["seq"] == 1
    assert entries[0]["phase"] == "parse"
    assert entries[0]["prev_hash"] == "0" * 64
    assert len(entries[0]["entry_hash"]) == 64

def test_append_chains_hashes(tmp_path):
    log_path = tmp_path / "log.jsonl"
    for i in range(3):
        subprocess.run(
            [sys.executable, f"{LIB_DIR}/decision_log.py", "append",
             "--log", str(log_path),
             "--phase", "generate",
             "--action", "wrote_file",
             "--detail", f"file_{i}.py"],
            capture_output=True, text=True
        )
    entries = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
    assert len(entries) == 3
    assert entries[0]["seq"] == 1
    assert entries[1]["seq"] == 2
    assert entries[2]["seq"] == 3
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert entries[2]["prev_hash"] == entries[1]["entry_hash"]

def test_append_hash_determinism(tmp_path):
    log_path = tmp_path / "log.jsonl"
    subprocess.run(
        [sys.executable, f"{LIB_DIR}/decision_log.py", "append",
         "--log", str(log_path),
         "--phase", "test", "--action", "test", "--detail", "test"],
        capture_output=True, text=True
    )
    entry = json.loads(log_path.read_text().strip())
    int(entry["entry_hash"], 16)  # valid hex
