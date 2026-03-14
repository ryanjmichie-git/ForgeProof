# Security Notes

## Key Handling Guidance

- Private signing keys are raw 32-byte Ed25519 seeds.
- Never commit private keys to version control.
- Store keys in local secure storage and rotate as needed.
- Use `--pubkey` output to export/share public verification key material.

See `docs/KEYS.md` for exact key format details.

## Ed25519 Implementation Warning (MVP)

Current Ed25519 operations are implemented in pure Python for MVP portability and testability.
This is not intended as hardened constant-time production cryptography.
For high-assurance deployments, migrate signing/verification to a vetted crypto library or HSM-backed flow.

## Determinism Guarantees

RPB enforces deterministic behavior for:

- canonical JSON serialization (`MANIFEST.json`, `HASHES.json`, `POLICY.json`),
- archive entry ordering and normalized TAR metadata,
- root digest definition.

Evidence timestamps are real-time when tests are run and therefore make evidence-bearing packs time-varying.

## Threat Model (MVP)

RPB is designed to detect:

- post-pack tampering of files/hashes,
- signature misuse or key mismatch,
- unsupported or policy-invalid claims.

RPB does not directly defend against:

- compromised developer machines,
- malicious test commands chosen by pack authors,
- weak operational key management.
