# tests/test_skill_ed25519.py
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib"))

def test_sign_verify_roundtrip():
    from rpb.ed25519 import sign, verify, derive_public_key
    key = os.urandom(32)
    pub = derive_public_key(key)
    msg = b"test message"
    sig = sign(key, msg)
    assert verify(pub, msg, sig)

def test_verify_rejects_wrong_message():
    from rpb.ed25519 import sign, verify, derive_public_key
    key = os.urandom(32)
    pub = derive_public_key(key)
    sig = sign(key, b"correct")
    assert not verify(pub, b"wrong", sig)

def test_verify_rejects_wrong_key():
    from rpb.ed25519 import sign, verify, derive_public_key
    key1 = os.urandom(32)
    key2 = os.urandom(32)
    pub2 = derive_public_key(key2)
    sig = sign(key1, b"msg")
    assert not verify(pub2, b"msg", sig)

def test_generate_ephemeral_keypair():
    from rpb.ed25519 import generate_ephemeral_keypair, verify, sign
    private, public = generate_ephemeral_keypair()
    assert len(private) == 32
    assert len(public) == 32
    sig = sign(private, b"test")
    assert verify(public, b"test", sig)

def test_generate_ephemeral_keypair_unique():
    from rpb.ed25519 import generate_ephemeral_keypair
    kp1 = generate_ephemeral_keypair()
    kp2 = generate_ephemeral_keypair()
    assert kp1[0] != kp2[0]
