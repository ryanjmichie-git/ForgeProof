# ForgeProof Claude Code Skill — Design Spec

**Date:** 2026-03-31
**Status:** Draft
**Author:** Ryan Michie + Claude

---

## 1. Problem

ForgeProof converts issues into working code with cryptographically signed provenance. Currently it runs as a standalone CI pipeline requiring GitLab, Anthropic API keys, and Docker. This makes it inaccessible to most developers.

The goal is to package ForgeProof as a Claude Code skill so any developer can type `/forgeproof 42` in their repo and get the full pipeline — no server, no API keys (beyond Claude Code itself), no CI setup.

## 2. Target User

A developer using Claude Code who wants to:
1. Point at a GitHub issue and get a working implementation with tests
2. Have every AI-generated change cryptographically signed for auditability
3. Optionally push the result as a PR

They are already in their repo directory in Claude Code. They may or may not have a `.forgeproof.toml` config file.

## 3. Commands

### `/forgeproof <issue-number>`

Full 4-phase pipeline: parse the issue, generate code + tests, evaluate (run tests/lint), sign provenance bundle.

**Input:** GitHub issue number (integer). The repo and owner are inferred from the current git remote.

**Output:** Files written locally + `.forgeproof/issue-<N>.rpack` bundle. No commits, no pushes — the user reviews first.

### `/forgeproof push`

After reviewing local changes from a `/forgeproof` run: create a branch, commit, push, and open a PR on GitHub.

**Input:** None (uses state from the previous run stored in `.forgeproof/last-run.json`).

**Output:** PR URL printed to terminal.

### `/forgeproof verify <path>`

Verify an `.rpack` bundle's signatures and hash chain integrity.

**Input:** Path to an `.rpack` file.

**Output:** Verification report (pass/fail, signer public key, hash chain status).

## 4. Architecture

### 4.1 No Anthropic API calls

This is the key architectural insight: Claude Code's Claude instance *is* the reasoning engine. The current ForgeProof calls `anthropic.Anthropic().messages.create()` for planning, code generation, and evaluation. In the skill version, Claude does this natively — the skill prompt guides it through the workflow using built-in tools (Read, Write, Edit, Bash, Grep, Glob).

This eliminates the `anthropic`, `httpx`, `pydantic`, `typer`, and `jinja2` dependencies entirely.

### 4.2 What Claude does vs. what Python scripts do

| Concern | Who handles it |
|---------|---------------|
| Pre-flight check (`gh auth status`) | Claude via Bash — abort with clear message if fails |
| Read GitHub issue | Claude via `gh issue view` (Bash) |
| Extract requirements from issue | Claude (native reasoning) |
| Plan file changes | Claude (native reasoning) |
| Scan existing repo structure | Claude via Read/Grep/Glob |
| Generate implementation code | Claude via Write/Edit |
| Generate tests | Claude via Write/Edit |
| Run tests | Claude via Bash (`pytest`) |
| Run linter | Claude via Bash (`ruff`) |
| Score requirements coverage | Claude (native reasoning) |
| Write `last-run.json` | Claude via Write tool (end of Phase 3) |
| Append decision log entries | Python helper (`lib/decision_log.py`) via Bash |
| Build + sign provenance bundle | Python script (`lib/provenance.py`) via Bash |
| Verify .rpack bundle | Python script (`lib/rpb/verify_signatures.py`) via Bash |
| Create PR | Claude via `gh pr create` (Bash) |

### 4.3 File structure

The skill uses Claude Code's **project-local custom commands** format (`.claude/commands/`), which is natively supported without plugin registration:

```
forgeproof-skill/                  # GitHub repo
├── README.md                      # Installation + usage guide
├── install.sh                     # Copies files into target project
├── commands/
│   ├── forgeproof.md              # /forgeproof <issue> orchestration prompt
│   ├── forgeproof-push.md         # /forgeproof-push prompt
│   └── forgeproof-verify.md       # /forgeproof-verify <path> prompt
├── lib/
│   ├── provenance.py              # CLI: build staging dir, MANIFEST, HASHES, sign, pack
│   ├── decision_log.py            # CLI: append hash-chained entries to decision log
│   ├── config.py                  # Load .forgeproof.toml with defaults (stdlib tomllib)
│   └── rpb/
│       ├── __init__.py
│       ├── ed25519.py             # Pure-Python RFC 8032 Ed25519 + ephemeral keygen
│       ├── canon.py               # Canonical JSON serialization (was internal/canon.py)
│       ├── hash.py                # SHA-256 utilities (was internal/hash.py)
│       ├── root_digest.py         # Root digest computation (was internal/root_digest.py)
│       ├── models.py              # Data classes: SignerInfo, etc. (was internal/rpb/models.py)
│       ├── staging.py             # Staging dir builder (was internal/rpb/staging.py)
│       ├── sign.py                # Key loading, signing (was internal/rpb/sign.py)
│       ├── verify_signatures.py   # Signature + hash chain verification
│       ├── pack_writer.py         # Deterministic PAX-format TAR creation
│       ├── pack_reader.py         # .rpack reading/extraction
│       └── pack_loader.py         # Load pack directory into memory
└── templates/
    └── pr_body.md                 # PR description template with provenance summary
```

#### Source file mapping from current codebase

| Skill `lib/rpb/` file | Source in current repo | Notes |
|---|---|---|
| `ed25519.py` | `Replication-Pack/internal/rpb/ed25519.py` | Add `generate_ephemeral_keypair()` |
| `canon.py` | `Replication-Pack/internal/canon.py` | Moved into `rpb/` package |
| `hash.py` | `Replication-Pack/internal/hash.py` | Moved into `rpb/` package |
| `root_digest.py` | `Replication-Pack/internal/root_digest.py` | Moved into `rpb/` package; update imports |
| `models.py` | `Replication-Pack/internal/rpb/models.py` | Direct copy |
| `staging.py` | `Replication-Pack/internal/rpb/staging.py` | Direct copy; update imports |
| `sign.py` | `Replication-Pack/internal/rpb/sign.py` | Add ephemeral key support; update imports |
| `verify_signatures.py` | `Replication-Pack/internal/rpb/verify_signatures.py` | Renamed from verify_signatures; update imports |
| `pack_writer.py` | `Replication-Pack/internal/rpb/pack_writer.py` | Update imports |
| `pack_reader.py` | `Replication-Pack/internal/rpb/pack_reader.py` | Update imports |
| `pack_loader.py` | `Replication-Pack/internal/rpb/pack_loader.py` | Update imports |

All `from internal.canon import ...` / `from internal.hash import ...` / `from internal.root_digest import ...` become `from rpb.canon import ...` etc. The `lib/` directory is added to `sys.path` at runtime by the CLI entry points.

### 4.4 Installation

After cloning the skill repo, the user runs the install script from their project root:

```bash
# Clone the skill repo
git clone https://github.com/ryanjmichie-git/forgeproof-skill ~/forgeproof-skill

# From your project directory:
~/forgeproof-skill/install.sh
```

The install script:
1. Copies `commands/*.md` into `.claude/commands/` (creates dir if needed)
2. Copies `lib/` into `.forgeproof/lib/` (the Python helper scripts)
3. Adds `.forgeproof/lib/` and `.forgeproof/ephemeral.*` to `.gitignore`
4. Prints confirmation

After install, `/forgeproof` is immediately available in Claude Code (no restart needed — `.claude/commands/` is auto-discovered).

### 4.5 State management

Each `/forgeproof` run writes a `.forgeproof/` directory in the repo root:

```
.forgeproof/
├── lib/                           # Installed helper scripts (gitignored)
├── last-run.json                  # Run metadata (written by Claude at end of Phase 3)
├── decision-log.jsonl             # Hash-chained AI decision log
├── issue-42.rpack                 # Signed provenance bundle (committed)
├── ephemeral.key                  # Ephemeral private key (gitignored, deleted after signing)
└── ephemeral.pub                  # Ephemeral public key (embedded in rpack, deleted locally)
```

**Gitignore rules** (added by install script):
```
.forgeproof/lib/
.forgeproof/ephemeral.*
.forgeproof/last-run.json
.forgeproof/decision-log.jsonl
```

The `.rpack` file is the only artifact that gets committed/pushed — it contains the public key and is self-verifiable.

`last-run.json` is written by Claude (via the Write tool) at the end of Phase 3, after evaluation completes:

```json
{
  "issue_number": 42,
  "issue_title": "Add CSV export endpoint",
  "repo": "ryanjmichie-git/ForgeProof",
  "branch": "forgeproof/issue-42",
  "files_changed": ["src/routes/export.py", "src/services/export.py", "tests/test_export.py"],
  "requirements": ["GET /export/csv returns CSV", "Include headers", "Handle empty data"],
  "requirements_met": 3,
  "requirements_total": 3,
  "tests_passed": 8,
  "tests_total": 8,
  "rpack_path": ".forgeproof/issue-42.rpack",
  "timestamp": "2026-03-31T14:30:00Z"
}
```

### 4.6 Decision log

The decision log uses a Python helper for reliable hash chaining. Claude cannot compute SHA-256 natively, so a small CLI handles it:

```bash
# Claude calls this at each phase boundary:
python .forgeproof/lib/decision_log.py append \
  --log .forgeproof/decision-log.jsonl \
  --phase parse \
  --action extracted_requirements \
  --detail "5 requirements from issue #42"
```

The helper:
1. Reads the last entry's `entry_hash` (or `"0" * 64` if first entry)
2. Builds the entry JSON with `seq`, `phase`, `action`, `detail`, `prev_hash`, `timestamp`
3. Computes `entry_hash = SHA-256(canonical_json(entry_without_hash))`
4. Appends the complete entry as one JSONL line

Entry schema (simplified from the original 17-field format — fields like `model_id`, `prompt_sha256` are not available in the skill context):

```json
{
  "seq": 1,
  "phase": "parse",
  "action": "extracted_requirements",
  "detail": "5 requirements from issue #42",
  "timestamp": "2026-03-31T14:30:00Z",
  "prev_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "entry_hash": "a1b2c3d4..."
}
```

### 4.7 Config: `.forgeproof.toml`

Optional. Uses TOML format (Python 3.11+ has `tomllib` in stdlib — no pip install needed). If absent, sensible defaults apply.

```toml
[paths]
allowed = ["src/**/*", "tests/**/*", "lib/**/*"]
denied = [".env", "**/*.key", "**/*.pem", ".github/**"]

[[evaluation.commands]]
name = "tests"
run = "pytest -q"
required = true

[[evaluation.commands]]
name = "lint"
run = "ruff check ."
required = false

[gates]
all_required_commands_pass = true
requirements_coverage_min = 80

[signing]
ephemeral = true
# key_path = "dev.key"   # Or use a persistent key
```

**Defaults when no config exists:**
- `paths.allowed`: `["src/**/*", "lib/**/*", "app/**/*", "tests/**/*"]`
- `paths.denied`: `[".env", "**/*.key", "**/*.pem", ".github/**", ".gitlab-ci.yml"]`
- `evaluation.commands`: auto-detected from project (pytest if `conftest.py` or `tests/` exists, ruff if `pyproject.toml` has `[tool.ruff]`)
- `signing.ephemeral`: `true`

## 5. Pipeline Detail

### Phase 0: Pre-flight

1. Claude runs `gh auth status` via Bash
2. If exit code is non-zero, Claude prints: "ForgeProof requires the GitHub CLI (`gh`) to be installed and authenticated. Run `gh auth login` first." and halts
3. Claude runs `gh repo view --json nameWithOwner -q .nameWithOwner` to get repo identifier
4. Claude checks for `.forgeproof.toml` and loads config (or uses defaults)
5. Claude verifies `python3 --version` is 3.11+ (needed for `tomllib`)

### Phase 1: Parse & Plan

1. Claude runs `gh issue view <N> --json title,body,labels,assignees`
2. Claude reads the issue body and extracts a numbered list of requirements (REQ-1, REQ-2, ...)
3. Claude scans the repo structure (Glob/Read) to understand existing code
4. Claude produces a plan: which files to create/modify, what each change accomplishes
5. Claude appends a `parse` decision log entry via: `python .forgeproof/lib/decision_log.py append --log .forgeproof/decision-log.jsonl --phase parse --action planned --detail "..."`
6. Claude presents the plan to the user and waits for approval before proceeding

### Phase 2: Generate

1. Claude writes implementation files using Write/Edit
2. Claude writes test files using Write/Edit
3. Claude respects `paths.allowed` and `paths.denied` from config
4. Claude appends `generate` decision log entries for each file written

### Phase 3: Evaluate

1. Claude runs each command from `evaluation.commands` via Bash
2. Claude captures stdout/stderr and exit codes
3. Claude maps test results back to requirements (REQ-1 covered by test_X, etc.)
4. If a required command fails, Claude attempts one fix iteration
5. If a required command still fails after the fix attempt, the pipeline halts with an error summary. Phase 4 is not executed. The user can fix issues manually and re-run
6. Claude appends `evaluate` decision log entries
7. Claude checks gates: do results meet `requirements_coverage_min`?
8. Claude writes `.forgeproof/last-run.json` via the Write tool with accumulated run state

### Phase 4: Package

1. Claude runs the provenance builder with explicit paths:
   ```bash
   python .forgeproof/lib/provenance.py build \
     --run-state .forgeproof/last-run.json \
     --decision-log .forgeproof/decision-log.jsonl \
     --config .forgeproof.toml \          # optional; uses defaults if absent
     --output .forgeproof/issue-42.rpack \
     --repo-root .
   ```
2. The provenance builder:
   - Reads `last-run.json` for metadata and file list
   - Reads `decision-log.jsonl` for the audit trail
   - Reads `.forgeproof.toml` (or defaults) for POLICY.json
   - Hashes each file in `files_changed` for HASHES.json
   - Builds MANIFEST.json (run metadata, file list, phase results)
   - Computes root digest: `SHA-256(canonical(MANIFEST) || canonical(HASHES) || canonical(POLICY))`
   - Generates ephemeral Ed25519 keypair via `os.urandom(32)` + `derive_public_key()`
   - Signs root digest, writes signature + public key to SIGNATURES/
   - Deletes the ephemeral private key from disk
   - Packs everything into deterministic PAX-format `.rpack` TAR
3. Claude reports the summary: files changed, tests passed, requirements met, rpack path

## 6. Prerequisites

The user needs:
- **Claude Code** installed and authenticated
- **`gh` CLI** installed and authenticated (for GitHub issue reading + PR creation)
- **Python 3.11+** (for provenance signing scripts — stdlib only, `tomllib` requires 3.11)
- **pytest** and/or **ruff** (only if they want evaluation — auto-detected, not required)

No Anthropic API key. No Docker. No CI. No pip install.

## 7. What's NOT in v1

- **GitHub Actions integration** — no CI pipeline, it's all local
- **MCP server** — deferred to v2 (Approach 3)
- **Multi-language code generation** — v1 generates Python; the evaluation runner is language-agnostic (any shell command works in config), but auto-detection and test generation target Python
- **GitLab support** — GitHub only in v1; GitLab can be added by swapping `gh` for `glab`
- **Persistent signing keys** — v1 defaults to ephemeral; persistent key support exists in config but isn't the primary flow
- **Team/org provenance policies** — single-developer workflow only

## 8. Migration Path to v2 (Skill + MCP Hybrid)

The v1 skill is designed so that v2 (MCP) is additive, not a rewrite:

1. `lib/` directory becomes the MCP server's tool implementations
2. The command prompts (`commands/*.md`) stay the same but call MCP tools instead of `python .forgeproof/lib/...`
3. `provenance.py build` becomes the `forgeproof_sign` MCP tool
4. `rpb/verify_signatures.py` becomes the `forgeproof_verify` MCP tool
5. A new `forgeproof_run` MCP tool wraps the full pipeline for non-Claude-Code clients

No user-facing behavior changes. The skill gets faster (MCP is a persistent process vs. spawning Python each time) and becomes usable from Claude Desktop, Cursor, etc.

## 9. Success Criteria

- A developer can install the skill, open a repo with a GitHub issue, run `/forgeproof <N>`, and get working code + tests + signed .rpack in under 5 minutes
- Zero external dependencies beyond Python 3.11+ stdlib, `gh` CLI, and Claude Code
- The .rpack bundle passes verification via `/forgeproof-verify`
- `/forgeproof-push` creates a clean PR with provenance summary in the description
