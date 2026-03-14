from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from internal.canon import dumps_canonical
from internal.hash import sha256_file
from internal.rpb import exit_codes
from internal.rpb.pack_reader import extract_rpack


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cmd" / "rpb.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _write_key(path: Path, seed: int) -> None:
    path.write_bytes(bytes(((seed + idx) % 256 for idx in range(32))))


def _write_json(path: Path, payload: dict) -> None:
    path.write_bytes(dumps_canonical(payload))


def _build_staged_p2_without_evidence(path: Path) -> None:
    (path / "VERIFY").mkdir(parents=True, exist_ok=True)
    (path / "SIGNATURES").mkdir(parents=True, exist_ok=True)
    (path / "VERIFY" / "verify_instructions.txt").write_text("verify", encoding="utf-8")

    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "p2-missing-evidence",
        "claims": [
            {
                "claim_id": "CLAIM-TESTED-001",
                "profile": "P2",
                "label": "tests passed",
                "properties": [],
            }
        ],
        "commands": {"build": [], "tests": [], "proofs": []},
        "evidence": [],
        "policy": {
            "policy_id": "default-mvp",
            "policy_version": "0.1.0",
            "policy_sha256": "0" * 64,
        },
        "signing": {"root_digest_sha256": "0" * 64, "signers": []},
    }
    policy = json.loads((ROOT / "schemas" / "POLICY.json").read_text(encoding="utf-8"))

    _write_json(path / "MANIFEST.json", manifest)
    _write_json(path / "POLICY.json", policy)

    hashes = {
        "hash_algo": "sha256",
        "generated_utc": "2026-01-01T00:00:00Z",
        "files": [],
    }
    for rel in ["MANIFEST.json", "POLICY.json", "VERIFY/verify_instructions.txt"]:
        fp = path / Path(rel)
        hashes["files"].append(
            {
                "path": rel,
                "sha256": sha256_file(fp),
                "size_bytes": fp.stat().st_size,
            }
        )
    _write_json(path / "HASHES.json", hashes)


class EvidenceAndRecheckTests(unittest.TestCase):
    def test_pack_with_tests_captures_evidence_and_verify_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            source.mkdir(parents=True, exist_ok=True)
            (source / "hello.txt").write_text("hello\n", encoding="utf-8")

            key = root / "devkey.ed25519"
            pub = root / "devkey.pub"
            pack = root / "tested_signed.rpack"
            _write_key(key, seed=51)

            pack_proc = _run_cli(
                "pack",
                str(source),
                "--output",
                str(pack),
                "--sign-key",
                str(key),
                "--pubkey",
                str(pub),
                "--tests",
                "python -c \"import sys; sys.exit(0)\"",
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)
            self.assertTrue(pack.exists())

            verify_proc = _run_cli("verify", str(pack), "--pubkey", str(pub), "--json")
            self.assertEqual(verify_proc.returncode, 0, verify_proc.stderr)
            payload = json.loads(verify_proc.stdout)
            self.assertTrue(payload["verified"])

            inspect_proc = _run_cli("inspect", str(pack), "--json")
            self.assertEqual(inspect_proc.returncode, 0, inspect_proc.stderr)
            inspect_payload = json.loads(inspect_proc.stdout)
            self.assertTrue(any(item.get("type") == "tests" for item in inspect_payload["evidence"]))

            extracted = root / "extract"
            extract_rpack(pack, extracted)
            self.assertTrue((extracted / "SOURCE" / "hello.txt").exists())
            self.assertTrue((extracted / "EVIDENCE" / "TESTS" / "test-001_stdout.txt").exists())
            self.assertTrue((extracted / "EVIDENCE" / "TESTS" / "test-001_stderr.txt").exists())

    def test_verify_recheck_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            source.mkdir(parents=True, exist_ok=True)
            (source / "hello.txt").write_text("hello\n", encoding="utf-8")

            key = root / "devkey.ed25519"
            pub = root / "devkey.pub"
            pack = root / "tested_signed.rpack"
            _write_key(key, seed=12)

            self.assertEqual(
                _run_cli(
                    "pack",
                    str(source),
                    "--output",
                    str(pack),
                    "--sign-key",
                    str(key),
                    "--pubkey",
                    str(pub),
                    "--tests",
                    "python -c \"import sys; sys.exit(0)\"",
                ).returncode,
                0,
            )

            recheck_proc = _run_cli("verify", str(pack), "--pubkey", str(pub), "--recheck", "--json")
            self.assertEqual(recheck_proc.returncode, 0, recheck_proc.stderr)
            payload = json.loads(recheck_proc.stdout)
            self.assertTrue(payload["verified"])

    def test_verify_recheck_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            source.mkdir(parents=True, exist_ok=True)
            (source / "hello.txt").write_text("hello\n", encoding="utf-8")

            sentinel = root / "sentinel.txt"
            sentinel.write_text("exists\n", encoding="utf-8")
            sentinel_expr = sentinel.as_posix()

            key = root / "devkey.ed25519"
            pub = root / "devkey.pub"
            pack = root / "tested_signed.rpack"
            _write_key(key, seed=77)

            command = (
                "python -c \"import pathlib,sys; "
                f"sys.exit(0 if pathlib.Path('{sentinel_expr}').exists() else 1)\""
            )
            self.assertEqual(
                _run_cli(
                    "pack",
                    str(source),
                    "--output",
                    str(pack),
                    "--sign-key",
                    str(key),
                    "--pubkey",
                    str(pub),
                    "--tests",
                    command,
                ).returncode,
                0,
            )

            sentinel.unlink()
            recheck_proc = _run_cli("verify", str(pack), "--pubkey", str(pub), "--recheck", "--json")
            self.assertEqual(recheck_proc.returncode, exit_codes.RECHECK_FAILED)
            payload = json.loads(recheck_proc.stdout)
            self.assertFalse(payload["verified"])

    def test_policy_enforcement_p2_missing_evidence_fails_exit_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged = root / "staged"
            staged.mkdir(parents=True, exist_ok=True)
            _build_staged_p2_without_evidence(staged)

            key = root / "devkey.ed25519"
            pub = root / "devkey.pub"
            pack = root / "p2-missing-evidence.rpack"
            _write_key(key, seed=101)

            pack_proc = _run_cli(
                "pack",
                str(staged),
                "--output",
                str(pack),
                "--sign-key",
                str(key),
                "--pubkey",
                str(pub),
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)

            verify_proc = _run_cli("verify", str(pack), "--pubkey", str(pub), "--json")
            self.assertEqual(verify_proc.returncode, exit_codes.POLICY_VIOLATION)
            payload = json.loads(verify_proc.stdout)
            self.assertFalse(payload["verified"])
            self.assertIn("policy_required_evidence_missing:tests", payload["failed_checks"])

    def test_pack_fails_when_test_command_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            source.mkdir(parents=True, exist_ok=True)
            (source / "hello.txt").write_text("hello\n", encoding="utf-8")

            pack = root / "should-not-exist.rpack"
            proc = _run_cli(
                "pack",
                str(source),
                "--output",
                str(pack),
                "--tests",
                "python -c \"import sys; sys.exit(9)\"",
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse(pack.exists())


if __name__ == "__main__":
    unittest.main()
