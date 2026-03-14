from __future__ import annotations

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from internal.root_digest import compute_root_digest
from internal.rpb.pack_loader import load_pack_directory
from internal.rpb.pack_reader import PackReadError, extract_rpack
from internal.rpb.pack_writer import create_rpack


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")


def _create_staging_pack(path: Path) -> None:
    (path / "SIGNATURES").mkdir(parents=True, exist_ok=True)
    (path / "VERIFY").mkdir(parents=True, exist_ok=True)
    (path / "VERIFY" / "verify_instructions.txt").write_text("offline verify stub", encoding="utf-8")
    (path / "README.txt").write_text("sample pack", encoding="utf-8")

    _write_json(
        path / "MANIFEST.json",
        {
            "schema_version": "rpb-manifest-0.1",
            "pack_id": "archive-determinism-pack",
            "claims": [{"claim_id": "CLAIM-P0-001", "profile": "P0"}],
            "evidence": [],
            "signing": {"signers": []},
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


class PackArchiveTests(unittest.TestCase):
    def test_archive_bytes_are_identical_across_rebuilds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            staging.mkdir(parents=True, exist_ok=True)
            _create_staging_pack(staging)

            first = root / "first.rpack"
            second = root / "second.rpack"
            create_rpack(staging, first)
            create_rpack(staging, second)

            self.assertEqual(first.read_bytes(), second.read_bytes())

            with tarfile.open(first, mode="r:*") as archive:
                names = [member.name for member in archive.getmembers()]
            self.assertEqual(names, sorted(names))

    def test_root_digest_is_stable_across_rebuilds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staging = root / "staging"
            staging.mkdir(parents=True, exist_ok=True)
            _create_staging_pack(staging)

            first = root / "first.rpack"
            second = root / "second.rpack"
            create_rpack(staging, first)
            create_rpack(staging, second)

            extracted_first = root / "out-first"
            extracted_second = root / "out-second"
            extract_rpack(first, extracted_first)
            extract_rpack(second, extracted_second)

            first_pack = load_pack_directory(extracted_first)
            second_pack = load_pack_directory(extracted_second)
            first_digest = compute_root_digest(first_pack.manifest, first_pack.hashes, first_pack.policy)
            second_digest = compute_root_digest(
                second_pack.manifest, second_pack.hashes, second_pack.policy
            )
            self.assertEqual(first_digest, second_digest)

    def test_extract_blocks_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            malicious = root / "malicious.rpack"
            with tarfile.open(malicious, mode="w", format=tarfile.PAX_FORMAT) as archive:
                payload = b"owned"
                info = tarfile.TarInfo(name="../escape.txt")
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))

            with self.assertRaises(PackReadError):
                extract_rpack(malicious, root / "out")


if __name__ == "__main__":
    unittest.main()

