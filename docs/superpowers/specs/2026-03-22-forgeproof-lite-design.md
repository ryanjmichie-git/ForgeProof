# ForgeProof Lite: Post-Commit Provenance Signing

**Date:** 2026-03-22
**Status:** Approved
**Branch:** `hackathon-native`

## Problem

The hackathon repo (`gitlab-ai-hackathon/participants/35326234`) cannot run custom CI jobs or inject API keys due to Pipeline Execution Policy restrictions and Developer-level permissions. ForgeProof's full pipeline (Claude API calls, Docker execution, MR creation) cannot run there. However, the cryptographic provenance signing — ForgeProof's core differentiator — requires no external APIs and can run locally.

## Solution

A post-commit git hook that automatically captures commit metadata and file hashes, then signs everything into a tamper-evident `.rpack` provenance bundle using the existing Replication-Pack (RPB) Ed25519 signing infrastructure. The `.rpack` files are committed to a `provenance/` directory and pushed to the hackathon repo alongside code changes.

## Architecture

```
git commit
  |
  +-- .githooks/post-commit (shell, ~5 lines)
       |
       +-- python scripts/forge_commit.py (~120 lines)
            |
            +-- 1. Capture: git log -1, git diff-tree HEAD
            +-- 2. Build: commit.json + file hashes
            +-- 3. Stage: MANIFEST.json, HASHES.json, POLICY.json
            +-- 4. Sign: Ed25519 via RPB write_signatures()
            +-- 5. Pack: .rpack via RPB create_rpack()
            +-- 6. Output: provenance/<short-sha>.rpack
```

## Components

### New Files

#### `scripts/forge_commit.py` (~150 lines)

Main script. No new dependencies — uses stdlib + existing RPB modules.

**Import path setup:** The script must add `Replication-Pack/` to `sys.path` before importing any RPB modules, using absolute paths derived from `__file__`:
```python
REPO_ROOT = Path(__file__).resolve().parents[1]
RPACK_ROOT = REPO_ROOT / "Replication-Pack"
sys.path.insert(0, str(RPACK_ROOT))
# Now RPB imports work: from internal.rpb.sign import write_signatures
```

**Responsibilities:**
- Run `git log -1 --format=...` to capture commit SHA, author, email, timestamp, message
- Run `git rev-parse --abbrev-ref HEAD` to capture branch name
- Run `git diff-tree --root --no-commit-id -r HEAD` to list changed files with status (A/M/D). The `--root` flag handles the initial commit (no parent).
- For merge commits: uses `-m --first-parent` to diff against the first parent only.
- Compute SHA-256 hash of each changed file that exists on disk. Deleted files (`status: "D"`) get `"sha256": null`.
- Build staging directory using RPB's `prepare_staging_directory()` from `staging.py`, then overlay `SOURCE/commit.json` with the commit metadata. Call `finalize_pack_metadata()` to rebuild HASHES.json and MANIFEST.json with all staging files (not just changed files).
- Call `write_signatures(staging, devkey_path)` to sign
- Call `create_rpack(staging, output_path)` to pack
- Copy `.rpack` to `provenance/<short-sha>.rpack`
- Clean up temp staging directory

**Recursion guard:** If the most recent commit message starts with `"provenance:"`, the script exits immediately to prevent infinite loops when provenance commits trigger the hook.

**Error handling:** All failures are caught and logged to `$REPO_ROOT/.forge-commit.log`. The hook never blocks a commit (`|| true` in the shell wrapper).

#### `.githooks/post-commit` (~5 lines)

```bash
#!/bin/bash
# ForgeProof Lite: sign commit provenance
REPO_ROOT="$(git rev-parse --show-toplevel)"
python "$REPO_ROOT/scripts/forge_commit.py" 2>>"$REPO_ROOT/.forge-commit.log" || true
```

#### `provenance/.gitkeep`

Empty file to ensure the directory is tracked by git.

### Modified Files

#### `README.md`

Add a "Provenance Verification" section explaining:
- What `.rpack` files are
- How to verify: `cd Replication-Pack && python cmd/rpb.py verify ../provenance/<sha>.rpack --pubkey devkey.ed25519`
- How to set up the hook: `git config core.hooksPath .githooks`

### Existing Files Reused (No Modifications)

| File | Function | Purpose |
|------|----------|---------|
| `Replication-Pack/internal/rpb/staging.py` | `prepare_staging_directory()`, `finalize_pack_metadata()` | Staging dir creation, metadata finalization |
| `Replication-Pack/internal/rpb/sign.py` | `write_signatures()` | Ed25519 signing |
| `Replication-Pack/internal/rpb/pack_writer.py` | `create_rpack()` | Deterministic TAR packing |
| `Replication-Pack/internal/hash.py` | `sha256_file()` | File hashing |
| `Replication-Pack/internal/canon.py` | `dumps_canonical()` | Canonical JSON serialization |
| `Replication-Pack/internal/root_digest.py` | `compute_root_digest()` | Root digest computation |
| `Replication-Pack/devkey.ed25519` | — | 32-byte Ed25519 signing key |

## Data Model

### commit.json

```json
{
  "schema_version": "forgeproof-lite-0.1",
  "commit_sha": "a6cdab4f...",
  "parent_sha": "cec30208...",
  "author": "Ryan Michie",
  "email": "ryan@example.com",
  "timestamp": "2026-03-22T15:30:00Z",
  "message": "feat: add health check endpoint",
  "branch": "hackathon-native",
  "changed_files": [
    {"path": "src/api/routes.py", "sha256": "abc123...", "status": "M"},
    {"path": "tests/test_health.py", "sha256": "def456...", "status": "A"},
    {"path": "old_file.py", "sha256": null, "status": "D"}
  ]
}
```

**Notes:**
- `parent_sha` is `null` for the initial commit (no parent)
- `sha256` is `null` for deleted files (status "D") since the file no longer exists on disk

### MANIFEST.json and POLICY.json

Generated by RPB's `prepare_staging_directory()` and `finalize_pack_metadata()` — not built manually. This ensures:
- MANIFEST has all required fields (`pack_id`, `producer`, `artifacts`, `signing.root_digest_sha256`, etc.)
- POLICY has `signature_thresholds` field required by the verifier
- HASHES.json covers all files in the staging directory (not just changed files)

The staging utilities produce verifier-compatible metadata automatically. We only need to write `SOURCE/commit.json` as our custom payload.

### Default POLICY.json (from RPB schemas/)

```json
{
  "schema_version": "rpb-policy-0.1",
  "policy_id": "forgeproof-lite-default",
  "policy_version": "0.1",
  "profiles": {"P0": true, "P1": false, "P2": false, "P3": false},
  "signature_thresholds": {"P0": 1, "P1": 1, "P2": 1, "P3": 2},
  "requirements": {
    "P0": {
      "must_include_paths": ["MANIFEST.json", "HASHES.json"],
      "must_have_commands": [],
      "must_have_evidence_types": [],
      "must_reference_spec_properties": false
    }
  }
}
```

## Setup

One-time setup for any developer cloning the repo:

```bash
git config core.hooksPath .githooks
```

This tells git to use `.githooks/` instead of `.git/hooks/`. The hook and script are committed to the repo, so they're available to anyone who clones it.

## Verification

```bash
# Verify a specific commit's provenance
cd Replication-Pack
python cmd/rpb.py verify ../provenance/<sha>.rpack --pubkey devkey.ed25519

# Expected output:
# {"verified": true, "claims_verified": ["CLAIM-INTEGRITY-001"], ...}
```

## Commit Workflow

The `.rpack` for commit X is created after commit X completes. It is **not** part of commit X — it appears as an untracked file. On the next commit, the previous `.rpack` is included. This means:

- Commit N includes the `.rpack` for commit N-1
- The latest commit's `.rpack` is always "pending" until the next commit
- Before pushing, the developer should `git add provenance/ && git commit -m "provenance: sign latest"` to include the most recent `.rpack`

**Recursion guard:** The post-commit hook checks if the commit message starts with `"provenance:"` and skips signing if so. This prevents infinite loops.

## Branch Strategy

- Create `hackathon-native` branch from `main`
- All ForgeProof Lite work happens on this branch
- The `provenance/` directory accumulates `.rpack` files as commits are made
- Main branch remains untouched (personal project demo)

## What Judges See

1. `provenance/` directory with real `.rpack` files — one per commit
2. Each `.rpack` is individually verifiable with `rpb verify`
3. Tamper any file and verification fails — demonstrable integrity
4. The git hook shows ForgeProof integrates into normal developer workflow
5. No external dependencies — pure Python, offline, self-contained

## Out of Scope

- Claude API calls (no API keys available)
- CI pipeline execution (policy blocked)
- MR creation (no GitLab token)
- Test execution or coverage scoring
- Docker image usage

## Testing

- Run `forge_commit.py` manually and verify it produces a valid `.rpack`
- Run `rpb verify` on the output to confirm signature validity
- Make a test commit with the hook enabled and confirm `.rpack` appears in `provenance/`
- Tamper with `commit.json` inside an extracted `.rpack` and confirm verification fails
