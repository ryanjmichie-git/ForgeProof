from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from internal.rpb import exit_codes
from internal.rpb.pack_reader import extract_rpack


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cmd" / "rpb.py"


def _write_key(path: Path, seed: int) -> None:
    path.write_bytes(bytes(((seed + idx) % 256 for idx in range(32))))


class PlainFolderPackTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_pack_plain_folder_builds_source_and_top_level_contract_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "hello.txt").write_text("hello world\n", encoding="utf-8")

            archive = root / "plain.rpack"
            proc = self._run("pack", str(input_dir), "--output", str(archive))
            self.assertEqual(proc.returncode, 0, proc.stderr)

            extracted = root / "extracted"
            extract_rpack(archive, extracted)
            self.assertTrue((extracted / "SOURCE" / "hello.txt").exists())
            self.assertTrue((extracted / "MANIFEST.json").exists())
            self.assertTrue((extracted / "HASHES.json").exists())
            self.assertTrue((extracted / "POLICY.json").exists())

            manifest = json.loads((extracted / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["claims"][0]["profile"], "P0")

    def test_pack_sign_verify_plain_folder_succeeds_for_p0(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "hello.txt").write_text("hello signed\n", encoding="utf-8")

            private_key = root / "sign.key"
            public_key = root / "sign.pub"
            archive = root / "signed.rpack"
            _write_key(private_key, seed=33)

            pack_proc = self._run(
                "pack",
                str(input_dir),
                "--output",
                str(archive),
                "--sign-key",
                str(private_key),
                "--pubkey",
                str(public_key),
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)

            verify_proc = self._run("verify", str(archive), "--pubkey", str(public_key), "--json")
            self.assertEqual(verify_proc.returncode, exit_codes.VERIFY_PASSED, verify_proc.stderr)
            payload = json.loads(verify_proc.stdout)
            self.assertTrue(payload["verified"])
            self.assertIn("CLAIM-INTEGRITY-001", payload["claims_verified"])


if __name__ == "__main__":
    unittest.main()

