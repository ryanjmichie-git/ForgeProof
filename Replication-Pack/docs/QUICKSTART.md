# Quickstart

## Prerequisites

- Python 3.11+
- Shell access (PowerShell or bash)
- Repository cloned locally

From repo root:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Generate a Dev Key

```powershell
python -c "import os; open('devkey.ed25519','wb').write(os.urandom(32))"
```

This file is a raw 32-byte Ed25519 private seed. Keep it secret.

## Build and Verify a Pack

Pack + sign + capture tests evidence:

```powershell
python cmd/rpb.py pack examples/complete-demo --output demo.rpack --sign-key devkey.ed25519 --tests "python -m unittest"
```

Offline verify:

```powershell
python cmd/rpb.py verify demo.rpack --pubkey devkey.ed25519
```

Offline verify plus test recheck:

```powershell
python cmd/rpb.py verify demo.rpack --pubkey devkey.ed25519 --recheck
```

Inspect claims/evidence/signers:

```powershell
python cmd/rpb.py inspect demo.rpack --json
```

## Normal Folder vs Staged Pack Root

- Normal folder input: `pack` auto-stages contents under `SOURCE/` and generates `MANIFEST.json`, `HASHES.json`, and `POLICY.json`.
- Staged pack root input: if `MANIFEST.json`, `HASHES.json`, and `POLICY.json` are already present, `pack` uses them directly.
