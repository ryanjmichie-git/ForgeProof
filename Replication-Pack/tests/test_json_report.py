from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from internal.rpb import exit_codes


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cmd" / "rpb.py"


def _write_key(path: Path, seed: int) -> None:
    path.write_bytes(bytes(((seed + idx) % 256 for idx in range(32))))


class VerifyJSONReportTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_verify_json_report_shape_and_stability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src"
            source.mkdir(parents=True, exist_ok=True)
            (source / "hello.txt").write_text("hello\n", encoding="utf-8")

            key = root / "devkey.ed25519"
            pack = root / "stable.rpack"
            _write_key(key, seed=141)

            pack_proc = self._run(
                "pack",
                str(source),
                "--output",
                str(pack),
                "--sign-key",
                str(key),
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)

            verify1 = self._run("verify", str(pack), "--pubkey", str(key), "--json")
            verify2 = self._run("verify", str(pack), "--pubkey", str(key), "--json")
            self.assertEqual(verify1.returncode, exit_codes.VERIFY_PASSED, verify1.stderr)
            self.assertEqual(verify2.returncode, exit_codes.VERIFY_PASSED, verify2.stderr)
            self.assertEqual(verify1.stdout, verify2.stdout)

            payload = json.loads(verify1.stdout)
            self.assertEqual(
                set(payload.keys()),
                {"verified", "failed_checks", "claims_verified", "claims_rejected", "signers"},
            )
            self.assertTrue(payload["verified"])
            self.assertIsInstance(payload["failed_checks"], list)
            self.assertIsInstance(payload["claims_verified"], list)
            self.assertIsInstance(payload["claims_rejected"], list)
            self.assertIsInstance(payload["signers"], list)
            self.assertIn('{"claims_rejected":', verify1.stdout)
            self.assertNotIn("created_utc", verify1.stdout)
            self.assertNotIn("started_utc", verify1.stdout)
            self.assertNotIn("ended_utc", verify1.stdout)


if __name__ == "__main__":
    unittest.main()

