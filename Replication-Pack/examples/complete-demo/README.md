# Complete Demo

This example demonstrates a full Replication Pack lifecycle with:

- `P0` claim: integrity over packaged content and metadata.
- `P2` claim: test command execution captured as evidence.

## What This Example Proves

- The source and metadata are packaged into a deterministic `.rpack`.
- The pack is signed with Ed25519.
- Offline verification validates signature, hashes, and policy constraints.
- `--recheck` reruns the declared test command and confirms it still passes.

## Project Contents

- `demo_math.py`: tiny module under test.
- `test_demo_math.py`: `unittest` test suite.
- `SPEC/PROP_ADD_COMMUTATIVE_001.md`: example specification property document.
- `run_demo.ps1`: one-command workflow script.

## Reproduce From Repo Root

```powershell
python -c "import os; open('devkey.ed25519','wb').write(os.urandom(32))"
python cmd/rpb.py pack examples/complete-demo --output demo.rpack --sign-key devkey.ed25519 --tests "python -m unittest"
python cmd/rpb.py verify demo.rpack --pubkey devkey.ed25519
python cmd/rpb.py verify demo.rpack --pubkey devkey.ed25519 --recheck
python cmd/rpb.py inspect demo.rpack --json
```

Expected result: each command exits successfully and verify outputs `verified: True`.
