import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib"))

def _make_minimal_pack(tmp_path):
    """Create a minimal valid pack directory for testing."""
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

def test_verify_unsigned_pack(tmp_path):
    from rpb.verify_signatures import verify_pack_directory
    pack_dir = _make_minimal_pack(tmp_path)
    outcome = verify_pack_directory(pack_dir)
    assert not outcome.result.verified

def test_verify_signed_pack(tmp_path):
    from rpb.verify_signatures import verify_pack_directory
    from rpb.sign import write_signatures
    from rpb.ed25519 import generate_ephemeral_keypair
    from rpb import exit_codes
    pack_dir = _make_minimal_pack(tmp_path)
    priv, pub = generate_ephemeral_keypair()
    key_path = tmp_path.parent / "test.key"
    key_path.write_bytes(priv)
    write_signatures(pack_dir, key_path)
    key_path.unlink()
    outcome = verify_pack_directory(pack_dir)
    assert outcome.exit_code in (exit_codes.VERIFY_PASSED, exit_codes.POLICY_VIOLATION)

def test_verify_tampered_pack(tmp_path):
    from rpb.verify_signatures import verify_pack_directory
    from rpb.sign import write_signatures
    from rpb.ed25519 import generate_ephemeral_keypair
    from rpb import exit_codes
    pack_dir = _make_minimal_pack(tmp_path)
    priv, pub = generate_ephemeral_keypair()
    key_path = tmp_path.parent / "test2.key"
    key_path.write_bytes(priv)
    write_signatures(pack_dir, key_path)
    key_path.unlink()
    manifest_path = pack_dir / "MANIFEST.json"
    manifest_path.write_text('{"tampered": true}')
    outcome = verify_pack_directory(pack_dir)
    assert not outcome.result.verified
