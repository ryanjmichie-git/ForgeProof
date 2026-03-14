# NEXT

## Completed: Milestone 2
- Added canonical JSON serializer (`internal/canon.py`) with stable keys and compact UTF-8 output.
- Added hashing utilities and HASHES writer with POSIX path normalization (`internal/hash.py`).
- Added root digest utility implementing `sha256(canon(MANIFEST)||canon(HASHES)||canon(POLICY))` (`internal/root_digest.py`).
- Added determinism-focused unit tests in `tests/test_determinism.py`.

## Completed: Milestone 3
- Added unpacked directory loader and required top-level file validation (`internal/rpb/pack_loader.py`).
- Added policy loading with required field checks and profile flag validation (`POLICY.json`).
- Wired `rpb inspect <directory>` to read real `MANIFEST.json` claims/evidence/signers with `--json` support.
- Added fail-fast inspect errors that return exit code 4 for invalid pack structure.
- Added tests for inspect success path and missing `MANIFEST.json`/`HASHES.json`/`POLICY.json`.

## Completed: Milestone 4
- Added deterministic `.rpack` TAR writer with fixed metadata and lexicographic entry ordering (`internal/rpb/pack_writer.py`).
- Added safe `.rpack` extractor with path traversal/link blocking (`internal/rpb/pack_reader.py`).
- Wired `rpb inspect` to accept either unpacked directories or `.rpack` archives.
- Added tests for deterministic archive bytes, stable root digest across rebuilds, and safe extraction path checks.

## Completed: Milestone 5
- Added Ed25519 signing with raw 32-byte private key input and derived public key output.
- Added signature artifact writing (`SIGNATURES/signer-1.json`, `SIGNATURES/signer-1.sig`, `SIGNATURES/signer-1.pub`).
- Implemented offline verification (hash validation, root digest recomputation, signature checks, policy threshold checks).
- Wired CLI `pack --sign-key [--pubkey]` and `verify [--pubkey]` for unpacked directories and `.rpack`.
- Added normal-folder auto-staging for `rpb pack <input_dir>` (builds `SOURCE/`, generated `MANIFEST/HASHES/POLICY`, then archives).
- Added milestone tests for valid signature, wrong key, tamper detection, and missing signature policy failure.
- Added key format and lookup documentation in `docs/KEYS.md`.

## Completed: Milestone 6
- Added test evidence runner (`internal/rpb/runner.py`) that executes commands and captures stdout/stderr/exit_code/timestamps under `EVIDENCE/TESTS/`.
- Extended `rpb pack` with `--tests` (repeatable) and `--no-tests`, and fail-fast behavior when tests fail (no `.rpack` output).
- Added manifest integration for tests: `commands.tests[]`, `evidence[]` entries, and automatic P2 claim when tests are executed.
- Implemented `verify --recheck` to rerun manifest-declared tests after offline checks and return exit code 5 on failure.
- Enforced policy requirements per claimed profile (including P2 required tests evidence with `exit_code=0`).
- Added integration tests for evidence capture, recheck success/failure, P2 policy violation, and pack-failure on failed tests.

## Completed: Milestone 7
- Added official end-to-end demo project under `examples/complete-demo/` with module, tests, SPEC property file, and workflow script.
- Improved CLI UX/help text for top-level, `pack`, and `verify`, including explicit verify exit-code documentation.
- Added onboarding/security/claims documentation: `docs/QUICKSTART.md`, `docs/CLAIMS.md`, `docs/SECURITY.md`.
- Added JSON report stability test coverage for `verify --json`.
- Added full lifecycle integration test (pack/sign/verify/recheck/tamper detection exit 3).
- Kept core deterministic archive + signing/verification behavior unchanged.

## TODO: Milestone 8
- Harden error UX consistency and include richer machine-readable failure taxonomy.
- Add deterministic evidence mode option for reproducible evidence-bearing packs.
- Expand policy validation depth and edge-case coverage (schema and semantic checks).
- Tighten documentation cross-linking and release-readiness checklist.
