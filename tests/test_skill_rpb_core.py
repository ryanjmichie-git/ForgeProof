# tests/test_skill_rpb_core.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib"))

def test_dumps_canonical_sorts_keys():
    from rpb.canon import dumps_canonical
    result = dumps_canonical({"b": 2, "a": 1})
    assert result == b'{"a":1,"b":2}'

def test_dumps_canonical_no_whitespace():
    from rpb.canon import dumps_canonical
    result = dumps_canonical({"key": [1, 2, 3]})
    assert b" " not in result

def test_loads_json_roundtrip():
    from rpb.canon import dumps_canonical, loads_json
    obj = {"hello": "world", "num": 42}
    assert loads_json(dumps_canonical(obj)) == obj

def test_sha256_bytes():
    from rpb.hash import sha256_bytes
    result = sha256_bytes(b"hello")
    assert len(result) == 64
    assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

def test_sha256_file(tmp_path):
    from rpb.hash import sha256_file
    f = tmp_path / "test.txt"
    f.write_bytes(b"hello")
    assert sha256_file(f) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

def test_normalize_manifest_path():
    from rpb.hash import normalize_manifest_path
    assert normalize_manifest_path("src\\main.py") == "src/main.py"
    assert normalize_manifest_path("src/main.py") == "src/main.py"

def test_compute_root_digest():
    from rpb.root_digest import compute_root_digest
    manifest = {"a": 1}
    hashes = {"b": 2}
    policy = {"c": 3}
    result = compute_root_digest(manifest, hashes, policy)
    assert len(result) == 64
    assert result == compute_root_digest(manifest, hashes, policy)
