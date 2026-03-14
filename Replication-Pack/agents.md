# agents.md — Codex operating guide for this repository

## Mission
You are implementing the Replication Pack Builder (RPB) MVP.
RPB produces a Replication Pack: a downloadable bundle with cryptographic signatures and evidence
so a third party can verify integrity and supported claims (e.g., tests passed; policy-gated
"MathSafe" only if evidence exists).

Your job is to:
1) keep work moving forward in small, verifiable increments,
2) preserve deterministic and auditable behavior,
3) never over-claim what the artifacts prove.

---

## Core rules (non-negotiable)

### 1) Always work in milestones with acceptance criteria
Before coding:
- Restate the milestone goal in 3–7 bullets.
- List acceptance criteria (tests, commands, expected output, exit codes).

After coding:
- Provide a short checklist: how to run + what success looks like.

### 2) Prefer small diffs and frequent checkpoints
- Make changes in small, reviewable commits (or clearly separated patches).
- Keep each milestone mergeable: tests must pass before moving on.

### 3) Determinism is a first-class requirement
- Archive creation must follow deterministic ordering and normalized metadata.
- Canonical JSON serialization must produce byte-stable output.
- Root digest must be stable for identical inputs.

If you introduce any non-determinism, document it and propose a fix.

### 4) Claims must be policy-gated
- A pack may not claim “MathSafe/bug-free/mathematically safe” unless policy allows the profile
  AND required proof evidence is present and validates.
- Default MVP policy must allow P0/P1/P2 and disallow P3 unless explicitly enabled.

### 5) Offline verification is the default
`rpb verify` must work without network access:
- verify signature(s)
- verify hashes
- enforce policy compliance
Optional `--recheck` may rerun tests if the pinned environment is available locally.

### 6) Never leak secrets
- Respect `.rpbignore` and default deny patterns (.env, keys, tokens).
- Do not print secrets into logs.
- Redactions must be recorded in the manifest (pattern + reason).

---

## Working style guidelines

### Write tests with every meaningful feature
- Add unit tests for canonicalization, hashing, root digest, and signature verification.
- Add integration tests for `pack -> verify` round-trip where feasible.

### When stuck, do the minimum to unblock
- If a “perfect” implementation is hard, ship a safe MVP version with clear TODOs.
- Never expand scope silently; propose scope changes explicitly.

### Output formats must be stable
- Manifest schema version and policy schema version are part of the public contract.
- Do not rename fields or change semantics without bumping schema_version.

---

## Repository conventions

### Paths and structure
Use these top-level directories:
- `schemas/` for JSON Schema files
- `examples/` for demo projects and scripts
- `docs/` for documentation
- `internal/` for implementation modules
- `cmd/` for CLI entrypoints

### Required pack structure (MVP)
Every `.rpack` must contain:
- `MANIFEST.json`, `HASHES.json`, `POLICY.json`
- `SIGNATURES/` directory with signer metadata and signature bytes
- `VERIFY/` directory with instructions
- optional `SPEC/`, `SOURCE/`, `EVIDENCE/`, `LOGS/`

---

## Execution and verification contract (MVP)

### Root digest definition
ROOT_DIGEST = sha256( canon(MANIFEST.json) || canon(HASHES.json) || canon(POLICY.json) )

### Exit codes
- 0: verify passed
- 2: signature invalid
- 3: hash mismatch / tampering
- 4: policy violation / unsupported claim
- 5: recheck failed (if requested)

### `rpb verify --json` report fields (minimum)
- `verified` (bool)
- `failed_checks` (array of strings)
- `claims_verified` (array)
- `claims_rejected` (array)
- `signers` (array with per-signer status)

---

## How to keep progress persistent (important)
When you finish a chunk:
1) Summarize what changed (3–7 bullets).
2) List commands to run to verify.
3) List next steps (3–7 bullets).
4) If any TODOs remain, put them in `docs/NEXT.md` and/or in code comments with a clear tag.

Never leave the project in a half-working state without calling it out.

---

## Communication norms in PR-style updates
When presenting changes:
- Include a concise diff summary (files touched + why).
- Provide exact commands for verification.
- Mention any known limitations explicitly.