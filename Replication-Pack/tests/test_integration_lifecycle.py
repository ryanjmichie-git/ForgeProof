from __future__ import annotations

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


class FullLifecycleIntegrationTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_full_lifecycle_pack_verify_recheck_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir(parents=True, exist_ok=True)

            (project / "app.py").write_text(
                "def square(v: int) -> int:\n"
                "    return v * v\n",
                encoding="utf-8",
            )
            (project / "test_app.py").write_text(
                "import unittest\n"
                "from app import square\n\n"
                "class AppTests(unittest.TestCase):\n"
                "    def test_square(self):\n"
                "        self.assertEqual(square(5), 25)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )

            key = root / "devkey.ed25519"
            pack = root / "workflow.rpack"
            _write_key(key, seed=209)

            pack_proc = self._run(
                "pack",
                str(project),
                "--output",
                str(pack),
                "--sign-key",
                str(key),
                "--tests",
                "python -m unittest",
            )
            self.assertEqual(pack_proc.returncode, 0, pack_proc.stderr)

            verify_proc = self._run("verify", str(pack), "--pubkey", str(key))
            self.assertEqual(verify_proc.returncode, exit_codes.VERIFY_PASSED, verify_proc.stderr)

            recheck_proc = self._run("verify", str(pack), "--pubkey", str(key), "--recheck")
            self.assertEqual(recheck_proc.returncode, exit_codes.VERIFY_PASSED, recheck_proc.stderr)

            extracted = root / "extracted"
            extract_rpack(pack, extracted)
            (extracted / "SOURCE" / "app.py").write_text(
                "def square(v: int) -> int:\n"
                "    return v + v\n",
                encoding="utf-8",
            )

            tamper_proc = self._run("verify", str(extracted), "--pubkey", str(key))
            self.assertEqual(tamper_proc.returncode, exit_codes.HASH_MISMATCH, tamper_proc.stderr)


if __name__ == "__main__":
    unittest.main()

