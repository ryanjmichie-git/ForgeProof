# tests/test_skill_rpb_sign.py
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib"))

def _make_minimal_pack(tmp_path):
    """Create a minimal valid pack directory for testing."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    from rpb.canon import dumps_canonical
    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "test-pack",
        "claims": [],
        "signing": {"root_digest_sha256": "0" * 64, "signers": []},
    }
    hashes = {"hash_algo": "sha256", "files": []}
    policy = {
        "schema_version": "rpb-policy-0.1",
        "policy_id": "test",
        "policy_version": "0.1.0",
        "profiles": {"P0": True, "P1": True, "P2": True, "P3": False},
        "signature_thresholds": {"P0": 1, "P1": 1, "P2": 1, "P3": 2},
        "requirements": {
            "P0": {"must_include_paths": [], "must_have_commands": [], "must_have_evidence_types": [], "must_reference_spec_properties": False},
            "P1": {"must_include_paths": [], "must_have_commands": [], "must_have_evidence_types": [], "must_reference_spec_properties": False},
            "P2": {"must_include_paths": [], "must_have_commands": [], "must_have_evidence_types": [], "must_reference_spec_properties": False},
            "P3": {"must_include_paths": [], "must_have_commands": [], "must_have_evidence_types": [], "must_reference_spec_properties": False},
        },
    }
    (tmp_path / "MANIFEST.json").write_bytes(dumps_canonical(manifest))
    (tmp_path / "HASHES.json").write_bytes(dumps_canonical(hashes))
    (tmp_path / "POLICY.json").write_bytes(dumps_canonical(policy))
    (tmp_path / "SIGNATURES").mkdir()
    return tmp_path

def test_load_pack_directory(tmp_path):
    from rpb.pack_loader import load_pack_directory
    pack_dir = _make_minimal_pack(tmp_path)
    pack = load_pack_directory(pack_dir)
    assert pack.manifest["pack_id"] == "test-pack"

def test_sign_and_verify_roundtrip(tmp_path):
    from rpb.sign import write_signatures
    from rpb.ed25519 import generate_ephemeral_keypair
    pack_dir = _make_minimal_pack(tmp_path)
    priv, pub = generate_ephemeral_keypair()
    key_path = tmp_path.parent / "ephemeral.key"
    key_path.write_bytes(priv)
    metadata = write_signatures(pack_dir, key_path)
    assert metadata["algorithm"] == "ed25519"
    assert (pack_dir / "SIGNATURES" / "signer-1.sig").exists()
    assert (pack_dir / "SIGNATURES" / "signer-1.pub").exists()
    key_path.unlink()

def test_create_and_extract_rpack(tmp_path):
    from rpb.pack_writer import create_rpack
    from rpb.pack_reader import extract_rpack
    pack_dir = _make_minimal_pack(tmp_path / "staging")
    rpack_path = tmp_path / "test.rpack"
    create_rpack(pack_dir, rpack_path)
    assert rpack_path.exists()
    extract_dir = tmp_path / "extracted"
    extract_rpack(rpack_path, extract_dir)
    assert (extract_dir / "MANIFEST.json").exists()
    assert (extract_dir / "HASHES.json").exists()
    assert (extract_dir / "POLICY.json").exists()
