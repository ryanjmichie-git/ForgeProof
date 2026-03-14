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


def _write_json(path: Path, payload: dict) -> None:
    path.write_bytes(dumps_canonical(payload))


def _create_pack_input(path: Path) -> None:
    (path / "VERIFY").mkdir(parents=True, exist_ok=True)
    (path / "VERIFY" / "verify_instructions.txt").write_text(
        "offline verification instructions", encoding="utf-8"
    )
    (path / "README.txt").write_text("sample payload", encoding="utf-8")
    (path / "SIGNATURES").mkdir(parents=True, exist_ok=True)

    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "milestone-5-pack",
        "claims": [
            {
                "claim_id": "CLAIM-P0-001",
                "profile": "P0",
                "label": "integrity",
                "properties": [],
            }
        ],
        "evidence": [],
        "commands": {"build": [], "tests": [], "proofs": []},
        "signing": {"signers": []},
        "policy": {
            "policy_id": "default-mvp",
            "policy_version": "0.1.0",
            "policy_sha256": "0" * 64,
        },
    }
    policy = {
        "schema_version": "rpb-policy-0.1",
        "policy_id": "default-mvp",
        "policy_version": "0.1.0",
        "profiles": {"P0": True, "P1": True, "P2": True, "P3": False},
        "signature_thresholds": {"P0": 1, "P1": 1, "P2": 1, "P3": 2},
        "requirements": {
            "P0": {
                "must_include_paths": ["MANIFEST.json", "HASHES.json", "SIGNATURES/"],
                "must_have_commands": [],
                "must_have_evidence_types": [],
                "must_reference_spec_properties": False,
            },
            "P1": {
                "must_include_paths": ["VERIFY/", "MANIFEST.json", "HASHES.json", "SIGNATURES/"],
                "must_have_commands": [],
                "must_have_evidence_types": [],
                "must_reference_spec_properties": False,
            },
            "P2": {
                "must_include_paths": ["EVIDENCE/TESTS/", "VERIFY/", "MANIFEST.json", "HASHES.json", "SIGNATURES/"],
                "must_have_commands": ["tests"],
                "must_have_evidence_types": ["tests"],
                "must_reference_spec_properties": False,
            },
            "P3": {
                "must_include_paths": ["SPEC/", "EVIDENCE/PROOFS/", "VERIFY/", "MANIFEST.json", "HASHES.json", "SIGNATURES/"],
                "must_have_commands": ["proofs"],
                "must_have_evidence_types": ["proofs"],
                "must_reference_spec_properties": True,
            },
        },
        "allowed_tools": {"build": [], "tests": [], "proofs": []},
    }

    _write_json(path / "MANIFEST.json", manifest)
    _write_json(path / "POLICY.json", policy)

    hashed_files = [
        "MANIFEST.json",
        "POLICY.json",
        "README.txt",
        "VERIFY/verify_instructions.txt",
    ]
    entries = []
    for relative in hashed_files:
        file_path = path / Path(relative)
        entries.append(
            {
                "path": relative,
                "sha256": sha256_file(file_path),
                "size_bytes": file_path.stat().st_size,
            }
        )

    hashes = {
        "hash_algo": "sha256",
        "generated_utc": "2026-01-01T00:00:00Z",
        "files": entries,
    }
    _write_json(path / "HASHES.json", hashes)


def _write_key(path: Path, seed: int) -> None:
    payload = bytes(((seed + idx) % 256 for idx in range(32)))
    path.write_bytes(payload)


class SignVerifyCLITests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_signature_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_input = root / "input"
            pack_input.mkdir(parents=True, exist_ok=True)
            _create_pack_input(pack_input)

            sign_key = root / "sign.key"
            pubkey = root / "sign.pub"
            archive = root / "signed.rpack"
            _write_key(sign_key, seed=7)

            pack_proc = self._run(
                "pack",
                str(pack_input),
                "--output",
                str(archive),
                "--sign-key",
                str(sign_key),
                "--pubkey",
                str(pubkey),
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)

            verify_proc = self._run("verify", str(archive), "--pubkey", str(pubkey), "--json")
            self.assertEqual(verify_proc.returncode, exit_codes.VERIFY_PASSED, verify_proc.stderr)
            payload = json.loads(verify_proc.stdout)
            self.assertTrue(payload["verified"])
            self.assertEqual(payload["failed_checks"], [])

    def test_signature_invalid_wrong_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_input = root / "input"
            pack_input.mkdir(parents=True, exist_ok=True)
            _create_pack_input(pack_input)

            sign_key = root / "sign.key"
            sign_pub = root / "sign.pub"
            wrong_key = root / "wrong.key"
            wrong_pub = root / "wrong.pub"
            archive = root / "signed.rpack"
            _write_key(sign_key, seed=12)
            _write_key(wrong_key, seed=90)

            self.assertEqual(
                self._run(
                    "pack",
                    str(pack_input),
                    "--output",
                    str(archive),
                    "--sign-key",
                    str(sign_key),
                    "--pubkey",
                    str(sign_pub),
                ).returncode,
                0,
            )
            self.assertEqual(
                self._run(
                    "pack",
                    str(pack_input),
                    "--output",
                    str(root / "other.rpack"),
                    "--sign-key",
                    str(wrong_key),
                    "--pubkey",
                    str(wrong_pub),
                ).returncode,
                0,
            )

            verify_proc = self._run("verify", str(archive), "--pubkey", str(wrong_pub), "--json")
            self.assertEqual(verify_proc.returncode, exit_codes.SIGNATURE_INVALID)

    def test_tamper_any_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_input = root / "input"
            pack_input.mkdir(parents=True, exist_ok=True)
            _create_pack_input(pack_input)

            sign_key = root / "sign.key"
            pubkey = root / "sign.pub"
            archive = root / "signed.rpack"
            _write_key(sign_key, seed=22)

            self.assertEqual(
                self._run(
                    "pack",
                    str(pack_input),
                    "--output",
                    str(archive),
                    "--sign-key",
                    str(sign_key),
                    "--pubkey",
                    str(pubkey),
                ).returncode,
                0,
            )

            extracted = root / "tampered"
            extract_rpack(archive, extracted)
            (extracted / "README.txt").write_text("tampered payload", encoding="utf-8")

            verify_proc = self._run("verify", str(extracted), "--pubkey", str(pubkey), "--json")
            self.assertEqual(verify_proc.returncode, exit_codes.HASH_MISMATCH)

    def test_missing_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_input = root / "input"
            pack_input.mkdir(parents=True, exist_ok=True)
            _create_pack_input(pack_input)

            archive = root / "unsigned.rpack"
            pack_proc = self._run("pack", str(pack_input), "--output", str(archive))
            self.assertEqual(pack_proc.returncode, 0)

            verify_proc = self._run("verify", str(archive), "--json")
            self.assertEqual(verify_proc.returncode, exit_codes.POLICY_VIOLATION)
            payload = json.loads(verify_proc.stdout)
            self.assertFalse(payload["verified"])


if __name__ == "__main__":
    unittest.main()
