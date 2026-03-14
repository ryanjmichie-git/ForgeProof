from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from internal.rpb import exit_codes
from internal.rpb.models import SignerStatus, VerificationResult


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cmd" / "rpb.py"


class ExitCodeContractTests(unittest.TestCase):
    def test_verify_exit_codes_match_mvp_contract(self) -> None:
        self.assertEqual(exit_codes.VERIFY_PASSED, 0)
        self.assertEqual(exit_codes.SIGNATURE_INVALID, 2)
        self.assertEqual(exit_codes.HASH_MISMATCH, 3)
        self.assertEqual(exit_codes.POLICY_VIOLATION, 4)
        self.assertEqual(exit_codes.RECHECK_FAILED, 5)


class VerificationResultTests(unittest.TestCase):
    def test_to_dict_has_required_verify_json_fields(self) -> None:
        result = VerificationResult(
            verified=False,
            failed_checks=["signature_invalid"],
            claims_verified=["P0"],
            claims_rejected=["P2"],
            signers=[SignerStatus(key_id="k1", status="invalid", reason="bad signature")],
        )

        payload = result.to_dict()
        self.assertIn("verified", payload)
        self.assertIn("failed_checks", payload)
        self.assertIn("claims_verified", payload)
        self.assertIn("claims_rejected", payload)
        self.assertIn("signers", payload)
        self.assertEqual(payload["signers"][0]["key_id"], "k1")


class CLIScaffoldTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_top_level_help_lists_subcommands(self) -> None:
        proc = self._run("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Replication Pack Builder", proc.stdout)
        self.assertIn("pack", proc.stdout)
        self.assertIn("verify", proc.stdout)
        self.assertIn("inspect", proc.stdout)

    def test_verify_help_has_json_and_recheck_flags(self) -> None:
        proc = self._run("verify", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--json", proc.stdout)
        self.assertIn("--recheck", proc.stdout)
        self.assertIn("Verify exit codes", proc.stdout)

    def test_pack_help_documents_auto_staging_and_tests(self) -> None:
        proc = self._run("pack", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("auto-staged under SOURCE/", proc.stdout)
        self.assertIn("--tests", proc.stdout)
        self.assertIn("--sign-key", proc.stdout)

    def test_verify_json_outputs_required_fields_and_contract_exit_code(self) -> None:
        proc = self._run("verify", "--json")
        self.assertEqual(proc.returncode, exit_codes.POLICY_VIOLATION)
        payload = json.loads(proc.stdout)
        self.assertIn("verified", payload)
        self.assertIn("failed_checks", payload)
        self.assertIn("claims_verified", payload)
        self.assertIn("claims_rejected", payload)
        self.assertIn("signers", payload)


if __name__ == "__main__":
    unittest.main()
