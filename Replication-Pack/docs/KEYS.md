# RPB Key Format (MVP)

RPB Milestone 5 uses **raw Ed25519 keys**:

- Private key file: exactly 32 bytes (`--sign-key` input)
- Public key file: exactly 32 bytes (`--pubkey` output for pack, optional input for verify)

No PEM/OpenSSH wrapping is used in this MVP.

## How `rpb pack` uses keys

When `--sign-key <path>` is provided:

1. `rpb pack` loads the 32-byte private key.
2. It derives the Ed25519 public key.
3. It computes `ROOT_DIGEST = sha256(canon(MANIFEST)||canon(HASHES)||canon(POLICY))`.
4. It signs the 32-byte root digest value.
5. It writes:
   - `SIGNATURES/signer-1.sig` (64-byte signature)
   - `SIGNATURES/signer-1.json` (metadata)
   - `SIGNATURES/signer-1.pub` (derived public key, raw 32 bytes)
6. If `--pubkey <path>` is provided, the same public key is also written there.

## How `rpb verify` resolves public key

`rpb verify` key lookup order:

1. `--pubkey <path>` if provided.
   For MVP convenience, this can be either:
   - a raw 32-byte public key, or
   - a raw 32-byte private seed (public key is derived automatically)
2. `public_key_hex` from signer metadata (`SIGNATURES/signer-1.json`)
3. `SIGNATURES/signer-1.pub` in the pack

## Minimal key generation example (Python)

```python
from pathlib import Path
import os

Path("dev-ed25519-private.key").write_bytes(os.urandom(32))
```

This file should be protected as a secret and never committed.
