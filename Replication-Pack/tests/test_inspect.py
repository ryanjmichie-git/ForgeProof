from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from internal.rpb import exit_codes
from internal.rpb.pack_writer import create_rpack


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cmd" / "rpb.py"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _create_valid_unpacked_pack(path: Path) -> None:
    _write_json(
        path / "MANIFEST.json",
        {
            "schema_version": "rpb-manifest-0.1",
            "pack_id": "demo-pack-1",
            "claims": [{"claim_id": "CLAIM-P0-001", "profile": "P0"}],
            "evidence": [{"evidence_id": "EVID-TESTS-001", "type": "tests"}],
            "signing": {"signers": ["dev-ed25519-key-01"]},
        },
    )
    _write_json(
        path / "HASHES.json",
        {
            "hash_algo": "sha256",
            "generated_utc": "2026-01-01T00:00:00Z",
            "files": [],
        },
    )
    _write_json(
        path / "POLICY.json",
        {
            "schema_version": "rpb-policy-0.1",
            "policy_id": "default-mvp",
            "policy_version": "0.1.0",
            "profiles": {"P0": True, "P1": True, "P2": True, "P3": False},
        },
    )


class InspectCommandTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_inspect_reads_manifest_from_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            _create_valid_unpacked_pack(pack_dir)

            proc = self._run("inspect", str(pack_dir), "--json")
            self.assertEqual(proc.returncode, exit_codes.VERIFY_PASSED)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["pack_id"], "demo-pack-1")
            self.assertEqual(payload["claims"][0]["claim_id"], "CLAIM-P0-001")
            self.assertEqual(payload["evidence"][0]["evidence_id"], "EVID-TESTS-001")
            self.assertEqual(payload["signers"], ["dev-ed25519-key-01"])

    def test_inspect_reads_manifest_from_rpack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack_dir = root / "pack"
            pack_dir.mkdir(parents=True, exist_ok=True)
            _create_valid_unpacked_pack(pack_dir)

            archive = root / "sample.rpack"
            create_rpack(pack_dir, archive)

            proc = self._run("inspect", str(archive), "--json")
            self.assertEqual(proc.returncode, exit_codes.VERIFY_PASSED)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["pack_id"], "demo-pack-1")
            self.assertEqual(payload["claims"][0]["claim_id"], "CLAIM-P0-001")

    def test_inspect_fails_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            _create_valid_unpacked_pack(pack_dir)
            (pack_dir / "MANIFEST.json").unlink()

            proc = self._run("inspect", str(pack_dir))
            self.assertEqual(proc.returncode, exit_codes.POLICY_VIOLATION)
            self.assertIn("missing required top-level file: MANIFEST.json", proc.stderr)

    def test_inspect_fails_when_hashes_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            _create_valid_unpacked_pack(pack_dir)
            (pack_dir / "HASHES.json").unlink()

            proc = self._run("inspect", str(pack_dir))
            self.assertEqual(proc.returncode, exit_codes.POLICY_VIOLATION)
            self.assertIn("missing required top-level file: HASHES.json", proc.stderr)

    def test_inspect_fails_when_policy_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pack_dir = Path(tmp)
            _create_valid_unpacked_pack(pack_dir)
            (pack_dir / "POLICY.json").unlink()

            proc = self._run("inspect", str(pack_dir))
            self.assertEqual(proc.returncode, exit_codes.POLICY_VIOLATION)
            self.assertIn("missing required top-level file: POLICY.json", proc.stderr)


if __name__ == "__main__":
    unittest.main()
