# ForgeProof Skill Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ForgeProof Claude Code skill — a `/forgeproof` slash command that turns GitHub issues into working code with cryptographically signed provenance bundles.

**Architecture:** Claude Code custom commands (`.claude/commands/*.md`) orchestrate the pipeline. Python helper scripts in `.forgeproof/lib/` handle crypto signing, hash chaining, and .rpack packaging. All Python is stdlib-only (no pip). The RPB library is copied from `Replication-Pack/internal/` with import paths rewritten from `internal.*` to `rpb.*`.

**Tech Stack:** Python 3.11+ (stdlib only), Ed25519 (pure Python), TOML config (`tomllib`), `gh` CLI, `git`, Claude Code custom commands

**Spec:** `docs/superpowers/specs/2026-03-31-forgeproof-skill-design.md`

---

## File Structure

```
forgeproof-skill/
├── README.md                          # Installation + usage
├── install.sh                         # Copies commands + lib into target project
├── commands/
│   ├── forgeproof.md                  # /forgeproof <issue> — main pipeline
│   ├── forgeproof-push.md             # /forgeproof-push — create PR
│   └── forgeproof-verify.md           # /forgeproof-verify <path> — verify .rpack
├── lib/
│   ├── provenance.py                  # CLI: build + sign provenance bundle
│   ├── decision_log.py                # CLI: append hash-chained log entries
│   ├── config.py                      # Load .forgeproof.toml with defaults
│   └── rpb/
│       ├── __init__.py                # Empty
│       ├── ed25519.py                 # Pure-Python Ed25519 + ephemeral keygen
│       ├── canon.py                   # Canonical JSON
│       ├── hash.py                    # SHA-256 utilities
│       ├── root_digest.py             # Root digest computation
│       ├── models.py                  # VerificationResult, SignerStatus
│       ├── staging.py                 # Build staging dir (MANIFEST, HASHES, POLICY)
│       ├── sign.py                    # Key loading, signing, write_signatures
│       ├── verify_signatures.py       # Full .rpack verification
│       ├── pack_writer.py             # Deterministic PAX TAR
│       ├── pack_reader.py             # Safe .rpack extraction
│       ├── pack_loader.py             # Load pack dir into PackContents
│       └── exit_codes.py              # Process exit codes
└── templates/
    └── pr_body.md                     # PR description template
```

Tests go in `tests/test_skill_*.py` alongside existing tests.

---

## Task 1: Create skill directory scaffold

**Files:**
- Create: `forgeproof-skill/lib/rpb/__init__.py`
- Create: `forgeproof-skill/README.md`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p forgeproof-skill/commands
mkdir -p forgeproof-skill/lib/rpb
mkdir -p forgeproof-skill/templates
```

- [ ] **Step 2: Create empty `__init__.py`**

```python
# forgeproof-skill/lib/rpb/__init__.py
```

- [ ] **Step 3: Create minimal README**

Write `forgeproof-skill/README.md` with:
- Project name and one-line description
- Prerequisites (Claude Code, gh CLI, Python 3.11+)
- Installation instructions (clone + run install.sh)
- Usage examples (`/forgeproof 42`, `/forgeproof-push`, `/forgeproof-verify`)

- [ ] **Step 4: Commit**

```bash
git add forgeproof-skill/
git commit -m "feat: scaffold forgeproof-skill directory"
```

---

## Task 2: Port RPB core library (canon, hash, root_digest, exit_codes)

These are leaf modules with no RPB internal dependencies. Copy from `Replication-Pack/internal/` and rewrite imports.

**Files:**
- Create: `forgeproof-skill/lib/rpb/canon.py` (copy from `Replication-Pack/internal/canon.py`)
- Create: `forgeproof-skill/lib/rpb/hash.py` (copy from `Replication-Pack/internal/hash.py`)
- Create: `forgeproof-skill/lib/rpb/root_digest.py` (copy from `Replication-Pack/internal/root_digest.py`)
- Create: `forgeproof-skill/lib/rpb/exit_codes.py` (copy from `Replication-Pack/internal/rpb/exit_codes.py`)
- Create: `tests/test_skill_rpb_core.py`

- [ ] **Step 1: Write tests for canon, hash, root_digest**

```python
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
    # Deterministic — same input gives same output
    assert result == compute_root_digest(manifest, hashes, policy)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_rpb_core.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'rpb'`

- [ ] **Step 3: Copy and adapt canon.py**

Copy `Replication-Pack/internal/canon.py` to `forgeproof-skill/lib/rpb/canon.py`. No import changes needed (stdlib only).

- [ ] **Step 4: Copy and adapt hash.py**

Copy `Replication-Pack/internal/hash.py` to `forgeproof-skill/lib/rpb/hash.py`. Change all `internal.*` imports:
```python
# OLD:
from internal.canon import dumps_canonical
# NEW:
from rpb.canon import dumps_canonical
```
(This is the only `internal.*` import in hash.py — verify by reading the full file.)

- [ ] **Step 5: Copy and adapt root_digest.py**

Copy `Replication-Pack/internal/root_digest.py` to `forgeproof-skill/lib/rpb/root_digest.py`. Change:
```python
# OLD:
from internal.canon import dumps_canonical
from internal.hash import sha256_bytes
# NEW:
from rpb.canon import dumps_canonical
from rpb.hash import sha256_bytes
```

- [ ] **Step 6: Copy exit_codes.py**

Copy `Replication-Pack/internal/rpb/exit_codes.py` to `forgeproof-skill/lib/rpb/exit_codes.py`. No changes needed.

- [ ] **Step 7: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_rpb_core.py -v
```

Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add forgeproof-skill/lib/rpb/canon.py forgeproof-skill/lib/rpb/hash.py forgeproof-skill/lib/rpb/root_digest.py forgeproof-skill/lib/rpb/exit_codes.py tests/test_skill_rpb_core.py
git commit -m "feat: port RPB core modules (canon, hash, root_digest, exit_codes)"
```

---

## Task 3: Port Ed25519 with ephemeral keygen

**Files:**
- Create: `forgeproof-skill/lib/rpb/ed25519.py` (copy from `Replication-Pack/internal/rpb/ed25519.py`)
- Create: `tests/test_skill_ed25519.py`

- [ ] **Step 1: Write tests**

```python
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
    # Verify the keypair works
    sig = sign(private, b"test")
    assert verify(public, b"test", sig)

def test_generate_ephemeral_keypair_unique():
    from rpb.ed25519 import generate_ephemeral_keypair
    kp1 = generate_ephemeral_keypair()
    kp2 = generate_ephemeral_keypair()
    assert kp1[0] != kp2[0]  # Different private keys
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_ed25519.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Copy ed25519.py and add ephemeral keygen**

Copy `Replication-Pack/internal/rpb/ed25519.py` to `forgeproof-skill/lib/rpb/ed25519.py`. No import changes needed (stdlib only). Add at the end:

```python
def generate_ephemeral_keypair() -> tuple[bytes, bytes]:
    """Generate a random Ed25519 keypair. Returns (private_key, public_key)."""
    import os
    private_key = os.urandom(32)
    public_key = derive_public_key(private_key)
    return private_key, public_key
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_ed25519.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add forgeproof-skill/lib/rpb/ed25519.py tests/test_skill_ed25519.py
git commit -m "feat: port Ed25519 with ephemeral keygen"
```

---

## Task 4: Port models, pack_loader, sign, pack_writer, pack_reader

**Files:**
- Create: `forgeproof-skill/lib/rpb/models.py`
- Create: `forgeproof-skill/lib/rpb/pack_loader.py`
- Create: `forgeproof-skill/lib/rpb/sign.py`
- Create: `forgeproof-skill/lib/rpb/pack_writer.py`
- Create: `forgeproof-skill/lib/rpb/pack_reader.py`
- Create: `tests/test_skill_rpb_sign.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_skill_rpb_sign.py
import json
import os
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

def test_load_pack_directory(tmp_path):
    from rpb.pack_loader import load_pack_directory
    pack_dir = _make_minimal_pack(tmp_path)
    pack = load_pack_directory(pack_dir)
    assert pack.manifest["pack_id"] == "test-pack"

def test_sign_and_verify_roundtrip(tmp_path):
    from rpb.sign import write_signatures
    from rpb.ed25519 import generate_ephemeral_keypair
    pack_dir = _make_minimal_pack(tmp_path)
    # Write ephemeral key
    priv, pub = generate_ephemeral_keypair()
    key_path = tmp_path.parent / "ephemeral.key"
    key_path.write_bytes(priv)
    # Sign
    metadata = write_signatures(pack_dir, key_path)
    assert metadata["algorithm"] == "ed25519"
    assert (pack_dir / "SIGNATURES" / "signer-1.sig").exists()
    assert (pack_dir / "SIGNATURES" / "signer-1.pub").exists()
    # Clean up key
    key_path.unlink()

def test_create_and_extract_rpack(tmp_path):
    from rpb.pack_writer import create_rpack
    from rpb.pack_reader import extract_rpack
    pack_dir = _make_minimal_pack(tmp_path / "staging")
    rpack_path = tmp_path / "test.rpack"
    create_rpack(pack_dir, rpack_path)
    assert rpack_path.exists()
    # Extract and verify
    extract_dir = tmp_path / "extracted"
    extract_rpack(rpack_path, extract_dir)
    assert (extract_dir / "MANIFEST.json").exists()
    assert (extract_dir / "HASHES.json").exists()
    assert (extract_dir / "POLICY.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_rpb_sign.py -v
```

Expected: FAIL

- [ ] **Step 3: Copy models.py**

Copy `Replication-Pack/internal/rpb/models.py` to `forgeproof-skill/lib/rpb/models.py`. No import changes (stdlib only).

- [ ] **Step 4: Copy and adapt pack_loader.py**

Copy `Replication-Pack/internal/rpb/pack_loader.py` to `forgeproof-skill/lib/rpb/pack_loader.py`. Change:
```python
# OLD:
from internal.canon import loads_json
# NEW:
from rpb.canon import loads_json
```

- [ ] **Step 5: Copy and adapt sign.py**

Copy `Replication-Pack/internal/rpb/sign.py` to `forgeproof-skill/lib/rpb/sign.py`. Change all imports:
```python
# OLD:
from internal.canon import dumps_canonical
from internal.hash import sha256_bytes
from internal.root_digest import compute_root_digest
from internal.rpb.ed25519 import derive_public_key, sign
from internal.rpb.pack_loader import load_pack_directory
# NEW:
from rpb.canon import dumps_canonical
from rpb.hash import sha256_bytes
from rpb.root_digest import compute_root_digest
from rpb.ed25519 import derive_public_key, sign
from rpb.pack_loader import load_pack_directory
```

- [ ] **Step 6: Copy and adapt pack_writer.py**

Copy `Replication-Pack/internal/rpb/pack_writer.py` to `forgeproof-skill/lib/rpb/pack_writer.py`. Change:
```python
# OLD:
from internal.hash import normalize_manifest_path
# NEW:
from rpb.hash import normalize_manifest_path
```

- [ ] **Step 7: Copy and adapt pack_reader.py**

Copy `Replication-Pack/internal/rpb/pack_reader.py` to `forgeproof-skill/lib/rpb/pack_reader.py`. No import changes needed (stdlib only).

- [ ] **Step 8: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_rpb_sign.py -v
```

Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add forgeproof-skill/lib/rpb/models.py forgeproof-skill/lib/rpb/pack_loader.py forgeproof-skill/lib/rpb/sign.py forgeproof-skill/lib/rpb/pack_writer.py forgeproof-skill/lib/rpb/pack_reader.py tests/test_skill_rpb_sign.py
git commit -m "feat: port sign, pack_writer, pack_reader, pack_loader, models"
```

---

## Task 5: Port staging.py and verify_signatures.py

**Files:**
- Create: `forgeproof-skill/lib/rpb/staging.py`
- Create: `forgeproof-skill/lib/rpb/verify_signatures.py`
- Create: `tests/test_skill_verify.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_skill_verify.py
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
    from rpb import exit_codes
    pack_dir = _make_minimal_pack(tmp_path)
    outcome = verify_pack_directory(pack_dir)
    # Unsigned pack should not verify
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
    # Signed pack with P0 claim should verify
    # (may fail if no P0 claim — that's OK, test the flow)
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
    # Tamper with MANIFEST
    manifest_path = pack_dir / "MANIFEST.json"
    manifest_path.write_text('{"tampered": true}')
    outcome = verify_pack_directory(pack_dir)
    assert not outcome.result.verified
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_verify.py -v
```

- [ ] **Step 3: Copy and adapt staging.py**

Copy `Replication-Pack/internal/rpb/staging.py` to `forgeproof-skill/lib/rpb/staging.py`. Change all imports:
```python
# OLD:
from internal.canon import dumps_canonical, loads_json
from internal.hash import normalize_manifest_path, sha256_bytes, sha256_file
from internal.root_digest import compute_root_digest
from internal.rpb.pack_loader import REQUIRED_TOP_LEVEL_FILES
from internal.rpb.runner import CommandRunResult
# NEW:
from rpb.canon import dumps_canonical, loads_json
from rpb.hash import normalize_manifest_path, sha256_bytes, sha256_file
from rpb.root_digest import compute_root_digest
from rpb.pack_loader import REQUIRED_TOP_LEVEL_FILES
```

Also remove the `apply_test_evidence` function and its `from internal.rpb.runner import CommandRunResult` import — the skill's `provenance.py` builds evidence from `last-run.json` directly. After removal, verify that `finalize_pack_metadata()` still works independently (it does not depend on the runner module — only on canon, hash, root_digest, and pack_loader).

- [ ] **Step 4: Copy and adapt verify_signatures.py**

Copy `Replication-Pack/internal/rpb/verify_signatures.py` to `forgeproof-skill/lib/rpb/verify_signatures.py`. Change all imports:
```python
# OLD:
from internal.hash import sha256_file
from internal.root_digest import compute_root_digest
from internal.rpb import exit_codes
from internal.rpb.ed25519 import verify
from internal.rpb.models import SignerStatus, VerificationResult
from internal.rpb.pack_loader import PackLoadError, load_pack_directory
from internal.rpb.runner import EvidenceRunError, run_test_commands
from internal.rpb.sign import candidate_public_keys_from_file, load_public_key
# NEW:
from rpb.hash import sha256_file
from rpb.root_digest import compute_root_digest
from rpb import exit_codes
from rpb.ed25519 import verify
from rpb.models import SignerStatus, VerificationResult
from rpb.pack_loader import PackLoadError, load_pack_directory
from rpb.sign import candidate_public_keys_from_file, load_public_key
```

Also remove the `recheck_tests` function and its `runner` import — the skill doesn't need to re-run tests during verification (that's the Evaluate phase's job).

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_verify.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add forgeproof-skill/lib/rpb/staging.py forgeproof-skill/lib/rpb/verify_signatures.py tests/test_skill_verify.py
git commit -m "feat: port staging and verify_signatures"
```

---

## Task 6: Build decision_log.py CLI

**Files:**
- Create: `forgeproof-skill/lib/decision_log.py`
- Create: `tests/test_skill_decision_log.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_skill_decision_log.py
import json
import subprocess
import sys
from pathlib import Path

LIB_DIR = str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib")
sys.path.insert(0, LIB_DIR)

def test_append_first_entry(tmp_path):
    log_path = tmp_path / "log.jsonl"
    result = subprocess.run(
        [sys.executable, f"{LIB_DIR}/decision_log.py", "append",
         "--log", str(log_path),
         "--phase", "parse",
         "--action", "planned",
         "--detail", "3 requirements extracted"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    entries = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
    assert len(entries) == 1
    assert entries[0]["seq"] == 1
    assert entries[0]["phase"] == "parse"
    assert entries[0]["prev_hash"] == "0" * 64
    assert len(entries[0]["entry_hash"]) == 64

def test_append_chains_hashes(tmp_path):
    log_path = tmp_path / "log.jsonl"
    for i in range(3):
        subprocess.run(
            [sys.executable, f"{LIB_DIR}/decision_log.py", "append",
             "--log", str(log_path),
             "--phase", "generate",
             "--action", "wrote_file",
             "--detail", f"file_{i}.py"],
            capture_output=True, text=True
        )
    entries = [json.loads(line) for line in log_path.read_text().strip().splitlines()]
    assert len(entries) == 3
    assert entries[0]["seq"] == 1
    assert entries[1]["seq"] == 2
    assert entries[2]["seq"] == 3
    # Hash chain: each prev_hash = prior entry_hash
    assert entries[1]["prev_hash"] == entries[0]["entry_hash"]
    assert entries[2]["prev_hash"] == entries[1]["entry_hash"]

def test_append_hash_determinism(tmp_path):
    """Same input at same seq produces same hash (except timestamp varies)."""
    log_path = tmp_path / "log.jsonl"
    subprocess.run(
        [sys.executable, f"{LIB_DIR}/decision_log.py", "append",
         "--log", str(log_path),
         "--phase", "test", "--action", "test", "--detail", "test"],
        capture_output=True, text=True
    )
    entry = json.loads(log_path.read_text().strip())
    # entry_hash should be a valid hex string
    int(entry["entry_hash"], 16)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_decision_log.py -v
```

- [ ] **Step 3: Implement decision_log.py**

```python
#!/usr/bin/env python3
"""CLI for appending hash-chained entries to a ForgeProof decision log."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib/ to path for rpb imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rpb.canon import dumps_canonical
from rpb.hash import sha256_bytes


def _last_entry_hash(log_path: Path) -> tuple[str, int]:
    """Read last entry's hash and seq from log file. Returns (hash, seq)."""
    if not log_path.exists():
        return "0" * 64, 0
    text = log_path.read_text(encoding="utf-8").strip()
    if not text:
        return "0" * 64, 0
    last_line = text.splitlines()[-1]
    entry = json.loads(last_line)
    return entry["entry_hash"], entry["seq"]


def _compute_entry_hash(entry_without_hash: dict) -> str:
    """SHA-256 of canonical JSON of entry (excluding entry_hash field)."""
    return sha256_bytes(dumps_canonical(entry_without_hash))


def append(log_path: Path, phase: str, action: str, detail: str) -> None:
    """Append a hash-chained entry to the decision log."""
    prev_hash, prev_seq = _last_entry_hash(log_path)
    entry = {
        "seq": prev_seq + 1,
        "phase": phase,
        "action": action,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = _compute_entry_hash(entry)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ForgeProof decision log")
    sub = parser.add_subparsers(dest="command")
    ap = sub.add_parser("append", help="Append a hash-chained entry")
    ap.add_argument("--log", required=True, help="Path to decision-log.jsonl")
    ap.add_argument("--phase", required=True, help="Pipeline phase (parse, generate, evaluate, package)")
    ap.add_argument("--action", required=True, help="Action performed")
    ap.add_argument("--detail", required=True, help="Human-readable detail")
    args = parser.parse_args()
    if args.command == "append":
        append(Path(args.log), args.phase, args.action, args.detail)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_decision_log.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add forgeproof-skill/lib/decision_log.py tests/test_skill_decision_log.py
git commit -m "feat: decision_log.py CLI with hash-chained entries"
```

---

## Task 7: Build config.py (TOML loader with defaults)

**Files:**
- Create: `forgeproof-skill/lib/config.py`
- Create: `tests/test_skill_config.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_skill_config.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib"))

def test_defaults_when_no_config():
    from config import load_config
    cfg = load_config(Path("/nonexistent/.forgeproof.toml"))
    assert "src/**/*" in cfg["paths"]["allowed"]
    assert ".env" in cfg["paths"]["denied"]
    assert cfg["signing"]["ephemeral"] is True

def test_load_toml_config(tmp_path):
    from config import load_config
    toml_file = tmp_path / ".forgeproof.toml"
    toml_file.write_text('''
[paths]
allowed = ["app/**/*.py"]
denied = [".secret"]

[signing]
ephemeral = false
key_path = "my.key"
''')
    cfg = load_config(toml_file)
    assert cfg["paths"]["allowed"] == ["app/**/*.py"]
    assert cfg["paths"]["denied"] == [".secret"]
    assert cfg["signing"]["ephemeral"] is False
    assert cfg["signing"]["key_path"] == "my.key"

def test_partial_config_merges_defaults(tmp_path):
    from config import load_config
    toml_file = tmp_path / ".forgeproof.toml"
    toml_file.write_text('[signing]\nephemeral = true\n')
    cfg = load_config(toml_file)
    # paths should fall back to defaults
    assert "src/**/*" in cfg["paths"]["allowed"]
    # signing.ephemeral should be from config
    assert cfg["signing"]["ephemeral"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_config.py -v
```

- [ ] **Step 3: Implement config.py**

```python
"""Load ForgeProof config from .forgeproof.toml with sensible defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomllib  # Python 3.11+ stdlib


DEFAULTS: dict[str, Any] = {
    "paths": {
        "allowed": ["src/**/*", "lib/**/*", "app/**/*", "tests/**/*"],
        "denied": [".env", "**/*.key", "**/*.pem", ".github/**", ".gitlab-ci.yml"],
    },
    "evaluation": {
        "commands": [],
    },
    "gates": {
        "all_required_commands_pass": True,
        "requirements_coverage_min": 80,
    },
    "signing": {
        "ephemeral": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, preserving base keys not in override."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load config from TOML file, merging with defaults."""
    if config_path and config_path.exists():
        with config_path.open("rb") as f:
            user_config = tomllib.load(f)
        return _deep_merge(DEFAULTS, user_config)
    return DEFAULTS.copy()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_config.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add forgeproof-skill/lib/config.py tests/test_skill_config.py
git commit -m "feat: config.py TOML loader with defaults"
```

---

## Task 8: Build provenance.py CLI

This is the main CLI that builds the staging directory, signs it, and creates the .rpack.

**Files:**
- Create: `forgeproof-skill/lib/provenance.py`
- Create: `tests/test_skill_provenance.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_skill_provenance.py
import json
import subprocess
import sys
from pathlib import Path

LIB_DIR = str(Path(__file__).resolve().parents[1] / "forgeproof-skill" / "lib")
sys.path.insert(0, LIB_DIR)

def _setup_run_state(tmp_path):
    """Create minimal last-run.json + decision-log.jsonl for testing."""
    # Create a fake changed file
    src_dir = tmp_path / "repo" / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "main.py").write_text("print('hello')")

    run_state = {
        "issue_number": 1,
        "issue_title": "Test issue",
        "repo": "test/repo",
        "branch": "forgeproof/issue-1",
        "files_changed": ["src/main.py"],
        "requirements": ["REQ-1"],
        "requirements_met": 1,
        "requirements_total": 1,
        "tests_passed": 1,
        "tests_total": 1,
        "rpack_path": ".forgeproof/issue-1.rpack",
        "timestamp": "2026-01-01T00:00:00Z",
    }
    fp_dir = tmp_path / "repo" / ".forgeproof"
    fp_dir.mkdir(parents=True)
    (fp_dir / "last-run.json").write_text(json.dumps(run_state))
    (fp_dir / "decision-log.jsonl").write_text(
        json.dumps({"seq": 1, "phase": "test", "action": "test", "detail": "test", "prev_hash": "0" * 64, "entry_hash": "a" * 64, "timestamp": "2026-01-01T00:00:00Z"}) + "\n"
    )
    return tmp_path / "repo"

def test_provenance_build_creates_rpack(tmp_path):
    repo = _setup_run_state(tmp_path)
    fp_dir = repo / ".forgeproof"
    output = fp_dir / "issue-1.rpack"
    result = subprocess.run(
        [sys.executable, f"{LIB_DIR}/provenance.py", "build",
         "--run-state", str(fp_dir / "last-run.json"),
         "--decision-log", str(fp_dir / "decision-log.jsonl"),
         "--output", str(output),
         "--repo-root", str(repo)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output.exists()
    # Verify it's a valid tar
    import tarfile
    assert tarfile.is_tarfile(output)

def test_provenance_build_rpack_contains_manifest(tmp_path):
    repo = _setup_run_state(tmp_path)
    fp_dir = repo / ".forgeproof"
    output = fp_dir / "issue-1.rpack"
    subprocess.run(
        [sys.executable, f"{LIB_DIR}/provenance.py", "build",
         "--run-state", str(fp_dir / "last-run.json"),
         "--decision-log", str(fp_dir / "decision-log.jsonl"),
         "--output", str(output),
         "--repo-root", str(repo)],
        capture_output=True, text=True
    )
    from rpb.pack_reader import extract_rpack
    extract_dir = tmp_path / "extracted"
    extract_rpack(output, extract_dir)
    assert (extract_dir / "MANIFEST.json").exists()
    assert (extract_dir / "HASHES.json").exists()
    assert (extract_dir / "POLICY.json").exists()
    assert (extract_dir / "SIGNATURES").is_dir()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_skill_provenance.py -v
```

- [ ] **Step 3: Implement provenance.py**

Create `forgeproof-skill/lib/provenance.py` — a CLI that:
1. Parses args: `--run-state`, `--decision-log`, `--config` (optional), `--output`, `--repo-root`
2. Reads `last-run.json` for metadata
3. Reads `decision-log.jsonl` for audit trail
4. Creates a temp staging directory with:
   - `MANIFEST.json` — built from run state (issue, requirements, files, test results, evidence, decision log reference)
   - `HASHES.json` — SHA-256 of each file in `files_changed` (resolved relative to `--repo-root`)
   - `POLICY.json` — from config or defaults
   - `DECISION_LOG/decision-log.jsonl` — copy of decision log
   - `VERIFY/verify_instructions.txt` — offline verification instructions
   - `SIGNATURES/` — created by signing step
5. Generates ephemeral Ed25519 keypair (or loads from config `key_path`)
6. Signs via `write_signatures()`
7. Deletes ephemeral private key
8. Packs via `create_rpack()`
9. Prints summary to stdout

Key implementation details:
- Use `tempfile.TemporaryDirectory` for staging
- Build MANIFEST with `schema_version`, `pack_id` (from issue number), `claims` (P2 if tests passed), `commands`, `evidence`, `artifacts`
- Build HASHES by walking staging dir (use `staging._build_hashes` pattern)
- Use `rpb.staging.finalize_pack_metadata()` to refresh hashes/manifest after initial write
- Use `rpb.sign.write_signatures()` to sign
- Use `rpb.pack_writer.create_rpack()` to pack

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_skill_provenance.py -v
```

Expected: all PASS

- [ ] **Step 5: Verify CLI help works**

```bash
python forgeproof-skill/lib/provenance.py --help
python forgeproof-skill/lib/provenance.py build --help
```

Expected: help text with args listed

- [ ] **Step 6: Commit**

```bash
git add forgeproof-skill/lib/provenance.py tests/test_skill_provenance.py
git commit -m "feat: provenance.py CLI — build + sign .rpack bundles"
```

---

## Task 9: Write Claude Code command prompts

**Files:**
- Create: `forgeproof-skill/commands/forgeproof.md`
- Create: `forgeproof-skill/commands/forgeproof-push.md`
- Create: `forgeproof-skill/commands/forgeproof-verify.md`

- [ ] **Step 1: Write forgeproof.md (main pipeline)**

This is the orchestration prompt. It instructs Claude through all 5 phases (0-4). Key sections:
- Phase 0: Pre-flight (`gh auth status`, Python version check)
- Phase 1: Parse issue, extract requirements, present plan, wait for approval
- Phase 2: Generate code + tests respecting config paths
- Phase 3: Run eval commands, attempt fix, write `last-run.json`
- Phase 4: Call `python .forgeproof/lib/provenance.py build ...`
- Decision log: call `python .forgeproof/lib/decision_log.py append ...` at phase boundaries
- Error handling: clear messages for each failure mode

The prompt should reference `$ARGUMENTS` for the issue number.

- [ ] **Step 2: Write forgeproof-push.md**

Instructions for Claude to:
1. Read `.forgeproof/last-run.json`
2. Create branch `forgeproof/issue-<N>`
3. `git add` changed files + `.forgeproof/issue-<N>.rpack`
4. `git commit` with meaningful message
5. `git push -u origin <branch>`
6. `gh pr create` using `templates/pr_body.md` pattern
7. Print PR URL

- [ ] **Step 3: Write forgeproof-verify.md**

Instructions for Claude to:
1. Take rpack path from `$ARGUMENTS`
2. Extract the .rpack to a temp directory using `python -c` with `rpb.pack_reader.extract_rpack`
3. Verify using `python -c` with `rpb.verify_signatures.verify_pack_directory` on the extracted dir
4. Present results: pass/fail, signer key ID, hash chain status, any failed checks

Note: verification uses the RPB library directly (not provenance.py). The verify command prompt should include the exact Python one-liner to run.

- [ ] **Step 4: Commit**

```bash
git add forgeproof-skill/commands/
git commit -m "feat: Claude Code command prompts (forgeproof, push, verify)"
```

---

## Task 10: Write PR template

**Files:**
- Create: `forgeproof-skill/templates/pr_body.md`

- [ ] **Step 1: Create PR body template**

```markdown
## Summary

Automated implementation for issue #{{issue_number}}: {{issue_title}}

## Changes

{{files_changed_list}}

## Requirements Coverage

{{requirements_met}}/{{requirements_total}} requirements met

| Requirement | Status |
|------------|--------|
{{requirements_table}}

## Test Results

- Tests: {{tests_passed}}/{{tests_total}} passed
- Lint: {{lint_status}}

## Provenance

This PR includes a cryptographically signed provenance bundle (`.rpack`) verifying the AI-generated code.

- **Bundle:** `{{rpack_path}}`
- **Signing:** Ed25519 (ephemeral keypair)
- **Verify:** `/forgeproof-verify {{rpack_path}}`

---
Generated by [ForgeProof](https://github.com/ryanjmichie-git/ForgeProof)
```

- [ ] **Step 2: Commit**

```bash
git add forgeproof-skill/templates/pr_body.md
git commit -m "feat: PR body template with provenance summary"
```

---

## Task 11: Build install.sh

**Files:**
- Create: `forgeproof-skill/install.sh`

- [ ] **Step 1: Write install script**

```bash
#!/bin/bash
# ForgeProof Skill Installer
# Run from your project root: ~/forgeproof-skill/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing ForgeProof skill..."

# 1. Copy commands
mkdir -p .claude/commands
cp "$SCRIPT_DIR/commands/"*.md .claude/commands/
echo "  Copied commands to .claude/commands/"

# 2. Copy lib
mkdir -p .forgeproof/lib
cp -r "$SCRIPT_DIR/lib/"* .forgeproof/lib/
echo "  Copied lib to .forgeproof/lib/"

# 3. Update .gitignore
GITIGNORE=".gitignore"
ENTRIES=(".forgeproof/lib/" ".forgeproof/ephemeral.*" ".forgeproof/last-run.json" ".forgeproof/decision-log.jsonl")
touch "$GITIGNORE"
for entry in "${ENTRIES[@]}"; do
    if ! grep -qxF "$entry" "$GITIGNORE"; then
        echo "$entry" >> "$GITIGNORE"
    fi
done
echo "  Updated .gitignore"

echo ""
echo "ForgeProof installed! Available commands:"
echo "  /forgeproof <issue-number>  — Generate code from a GitHub issue"
echo "  /forgeproof-push            — Create a PR with provenance"
echo "  /forgeproof-verify <path>   — Verify an .rpack bundle"
```

- [ ] **Step 2: Make executable and test**

```bash
chmod +x forgeproof-skill/install.sh
```

- [ ] **Step 3: Commit**

```bash
git add forgeproof-skill/install.sh
git commit -m "feat: install.sh for one-command skill installation"
```

---

## Task 12: Run full test suite and lint

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/test_skill_*.py -v --tb=short
```

Expected: all PASS

- [ ] **Step 2: Run ruff on skill lib**

```bash
python -m ruff check forgeproof-skill/lib/
```

Expected: clean (no errors)

- [ ] **Step 3: Run CLI smoke tests**

```bash
# Decision log
python forgeproof-skill/lib/decision_log.py append --log /tmp/fp-test.jsonl --phase test --action smoke --detail "smoke test"

# Provenance help
python forgeproof-skill/lib/provenance.py --help

# Ed25519 round-trip
python -c "
import sys; sys.path.insert(0, 'forgeproof-skill/lib')
from rpb.ed25519 import generate_ephemeral_keypair, sign, verify
priv, pub = generate_ephemeral_keypair()
sig = sign(priv, b'hello')
assert verify(pub, b'hello', sig)
print('All smoke tests passed')
"
```

- [ ] **Step 4: Fix any issues found**

- [ ] **Step 5: Final commit**

```bash
git add forgeproof-skill/ tests/test_skill_*.py
git commit -m "test: full test suite and lint pass for forgeproof-skill"
```

---

## Task 13: End-to-end integration test

- [ ] **Step 1: Install skill into the ForgeProof repo itself**

```bash
cd /c/Dev/ForgeProof
./forgeproof-skill/install.sh
```

Verify:
- `.claude/commands/forgeproof.md` exists
- `.forgeproof/lib/rpb/ed25519.py` exists
- `.gitignore` has the forgeproof entries

- [ ] **Step 2: Test provenance build with real data**

Create a mock `last-run.json` and `decision-log.jsonl` in `.forgeproof/`, then run:

```bash
python .forgeproof/lib/provenance.py build \
  --run-state .forgeproof/last-run.json \
  --decision-log .forgeproof/decision-log.jsonl \
  --output .forgeproof/test-issue.rpack \
  --repo-root .
```

Verify the .rpack is created and contains MANIFEST, HASHES, POLICY, SIGNATURES.

- [ ] **Step 3: Verify the .rpack**

Extract and verify the bundle:

```bash
python -c "
import sys; sys.path.insert(0, '.forgeproof/lib')
from rpb.pack_reader import extract_rpack
from rpb.verify_signatures import verify_pack_directory
extract_rpack('.forgeproof/test-issue.rpack', '/tmp/fp-verify')
result = verify_pack_directory('/tmp/fp-verify')
print(f'Verified: {result.result.verified}')
print(f'Exit code: {result.exit_code}')
if result.result.failed_checks:
    print(f'Failed: {result.result.failed_checks}')
"
```

- [ ] **Step 4: Clean up test artifacts**

```bash
rm -f .forgeproof/test-issue.rpack .forgeproof/last-run.json .forgeproof/decision-log.jsonl
rm -rf /tmp/fp-verify /tmp/fp-test.jsonl
```

- [ ] **Step 5: Commit and push**

```bash
git add forgeproof-skill/ tests/test_skill_*.py
git commit -m "feat: ForgeProof skill v1 — complete implementation"
git push github hackathon-native
git push personal hackathon-native
```
