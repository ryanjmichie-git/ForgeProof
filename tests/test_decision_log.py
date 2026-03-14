"""Tests for the hash-chained decision log."""

import tempfile
from pathlib import Path

from forgeproof.provenance.decision_log import DecisionLog


def test_append_and_chain():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "decision_log.jsonl"
        dl = DecisionLog(log_path)

        e1 = dl.append("parse_plan", decision_summary="Parsed issue")
        e2 = dl.append("generate", decision_summary="Generated code")
        e3 = dl.append("evaluate", decision_summary="Ran tests")

        assert e1["seq"] == 1
        assert e2["seq"] == 2
        assert e3["seq"] == 3

        # Chain links
        assert e1["prev_hash"] == "0" * 64
        assert e2["prev_hash"] == e1["entry_hash"]
        assert e3["prev_hash"] == e2["entry_hash"]

        # Verify the chain
        valid, errors = DecisionLog.verify_chain(log_path)
        assert valid, f"Chain verification failed: {errors}"
        assert errors == []


def test_verify_detects_tamper():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "decision_log.jsonl"
        dl = DecisionLog(log_path)
        dl.append("phase1", decision_summary="Step 1")
        dl.append("phase2", decision_summary="Step 2")

        # Tamper with the file
        lines = log_path.read_text(encoding="utf-8").splitlines()
        lines[0] = lines[0].replace("Step 1", "TAMPERED")
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        valid, errors = DecisionLog.verify_chain(log_path)
        assert not valid
        assert len(errors) > 0


def test_empty_log():
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "decision_log.jsonl"
        log_path.write_text("", encoding="utf-8")
        valid, errors = DecisionLog.verify_chain(log_path)
        assert valid
        assert errors == []
