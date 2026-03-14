from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from internal.canon import dumps_canonical
from internal.hash import normalize_manifest_path, write_hashes_json
from internal.root_digest import compute_root_digest


class CanonicalJSONTests(unittest.TestCase):
    def test_canonical_json_is_deterministic(self) -> None:
        obj = {
            "z": 1,
            "a": {
                "c": [3, 2, 1],
                "b": {"y": 2, "x": 1},
            },
        }

        first = dumps_canonical(obj)
        second = dumps_canonical(obj)

        self.assertEqual(first, second)
        self.assertIn(b'"a":{"b":{"x":1,"y":2},"c":[3,2,1]}', first)
        self.assertTrue(first.startswith(b'{"a":'))


class RootDigestTests(unittest.TestCase):
    def test_root_digest_changes_on_any_change(self) -> None:
        manifest = {
            "schema_version": "rpb-manifest-0.1",
            "claims": [{"claim_id": "C1", "profile": "P0"}],
        }
        hashes = {
            "hash_algo": "sha256",
            "files": [{"path": "MANIFEST.json", "sha256": "a" * 64, "size_bytes": 1}],
        }
        policy = {"schema_version": "rpb-policy-0.1", "profiles": {"P0": True, "P3": False}}

        baseline = compute_root_digest(manifest, hashes, policy)

        changed_manifest = {
            "schema_version": "rpb-manifest-0.1",
            "claims": [{"claim_id": "C2", "profile": "P0"}],
        }
        changed_hashes = {
            "hash_algo": "sha256",
            "files": [{"path": "MANIFEST.json", "sha256": "b" * 64, "size_bytes": 1}],
        }
        changed_policy = {"schema_version": "rpb-policy-0.1", "profiles": {"P0": True, "P3": True}}

        self.assertNotEqual(baseline, compute_root_digest(changed_manifest, hashes, policy))
        self.assertNotEqual(baseline, compute_root_digest(manifest, changed_hashes, policy))
        self.assertNotEqual(baseline, compute_root_digest(manifest, hashes, changed_policy))


class HashesPathTests(unittest.TestCase):
    def test_path_normalization(self) -> None:
        self.assertEqual(
            normalize_manifest_path(r"SOURCE\tests\test_safe_divide.py"),
            "SOURCE/tests/test_safe_divide.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "dir" / "child.txt"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text("hello", encoding="utf-8")

            out_path = root / "HASHES.json"
            write_hashes_json([source], out_path)

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            normalized = payload["files"][0]["path"]
            self.assertNotIn("\\", normalized)
            self.assertEqual(normalized, source.as_posix())


if __name__ == "__main__":
    unittest.main()
