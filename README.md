# ForgeProof

**AI agent that converts GitLab issues into review-ready merge requests with cryptographically signed provenance bundles.**

ForgeProof reads a GitLab issue, generates implementation code and tests using Claude, runs the tests, evaluates requirements coverage, and opens a merge request — all in a single CI pipeline. Every AI decision is recorded in a tamper-evident, Ed25519-signed provenance bundle (.rpack) that anyone can verify offline.

---

## How It Works

```
GitLab Issue                                         Merge Request
     |                                                    ^
     v                                                    |
 +----------+    +-----------+    +----------+    +-----------+
 |  Phase 1 | -> |  Phase 2  | -> | Phase 3  | -> |  Phase 4  |
 |  Parse & |    |  Generate |    | Evaluate |    |  Package  |
 |  Plan    |    |  Code &   |    | (pytest, |    | (.rpack + |
 |          |    |  Tests    |    |  ruff,   |    |  sign +   |
 |          |    |           |    |  score)  |    |  MR)      |
 +----------+    +-----------+    +----------+    +-----------+
      |               |               |                |
      v               v               v                v
   7 REQs         3 files        10 tests pass    Ed25519 signed
   2 steps        generated      100% coverage    .rpack bundle
```

| Phase | What happens | Claude calls |
|-------|-------------|--------------|
| **Parse & Plan** | Extracts requirements from issue, plans file changes | 1 |
| **Generate** | Writes implementation code and tests | 2 |
| **Evaluate** | Runs pytest + ruff, scores requirements coverage | 1 |
| **Package** | Signs provenance bundle, creates branch + MR, posts comment | 0 |

---

## Key Features

### Cryptographic Provenance (.rpack)
Every pipeline run produces a `.rpack` bundle containing:
- **MANIFEST.json** — Run metadata, phase results, file list
- **HASHES.json** — SHA-256 hash of every artifact
- **DECISION_LOG.jsonl** — Hash-chained log of every AI decision (model, prompt hash, response hash)
- **SIGNATURES/** — Ed25519 signature over the root digest
- **EVIDENCE/** — Test output (stdout/stderr, exit codes)

The root digest binds everything: `SHA-256(canonical(MANIFEST) || canonical(HASHES) || canonical(POLICY))`. Change one byte and verification fails.

### Self-Evaluating
ForgeProof doesn't just generate code — it tests it. The eval phase:
- Installs target project dependencies
- Runs pytest against generated code
- Runs ruff linter
- Uses Claude to score each requirement as covered/not covered
- Gates: all required checks must pass AND coverage >= 80% to be "review-ready"

### Offline Verification
```bash
python Replication-Pack/cmd/rpb.py verify <pack.rpack> --pubkey Replication-Pack/devkey.ed25519
```
No network needed. Checks signature validity, hash integrity, and policy compliance.

### Hash-Chained Decision Log
Every AI interaction is appended to a JSONL log where each entry contains:
- Previous entry's SHA-256 hash (creating a chain)
- Model ID, temperature, prompt/response hashes
- Phase, timestamp, status

Tampering with any entry breaks the chain — detectable by `verify_chain()`.

---

## Quick Start

### Run Locally
```bash
# Install
pip install -e ".[dev]"

# Run against a markdown issue file
python -m forgeproof.main run --issue demo/sample-issue.md --repo . --verbose
```

### Run in GitLab CI
1. Push to GitLab
2. Set CI variables: `ANTHROPIC_API_KEY`, `GITLAB_TOKEN` (PAT with `api` scope)
3. Create an issue with acceptance criteria
4. Run pipeline: CI/CD -> Pipelines -> Run pipeline -> set `ISSUE_IID=<number>`
5. ForgeProof creates a branch, commits code, opens an MR, and uploads the .rpack artifact

### Verify a Provenance Bundle
```bash
# Download .rpack from pipeline artifacts, then:
python Replication-Pack/cmd/rpb.py verify <pack.rpack> --pubkey Replication-Pack/devkey.ed25519
```

---

## Project Structure

```
src/forgeproof/          # Core agent
  main.py                # CLI entrypoint
  orchestrator.py        # 4-phase pipeline runner
  config.py              # .forgeproof.yml + env var loading
  models.py              # Pydantic data models
  claude/                # Claude API client, prompts, recorder
  context/               # Issue parsing, repo scanning
  gitlab/                # GitLab REST API, MR creation
  phases/                # parse_plan, generate, evaluate
  provenance/            # Decision log, .rpack packer, manifest

Replication-Pack/        # RPB: Ed25519 signing, verification, deterministic packing
demo/seed-repo/          # Embedded FastAPI project (ForgeProof's target)
agents/agent.yml         # GitLab Duo AI Catalog registration
tests/                   # 137 tests across 12 files (71% module coverage)
```

---

## Configuration

Create `.forgeproof.yml` in your repo root:

```yaml
allowed_paths:
  - "src/**/*.py"
  - "tests/**/*.py"

denied_paths:
  - ".env"
  - "**/*.key"
  - ".gitlab-ci.yml"

evaluation:
  commands:
    - name: tests
      run: "python -m pytest -q"
      required: true
    - name: lint
      run: "python -m ruff check ."
      required: true

gates:
  all_required_commands_pass: true
  requirements_coverage_min: 80

signing:
  key_path: "devkey.ed25519"
  policy_profile: "P2"
```

---

## Pipeline Results (Live Demo)

From a real pipeline run on GitLab CI:

- **Issue:** "Add health check endpoint" (7 acceptance criteria)
- **Generated:** 3 files (routes.py, test_health.py x2)
- **Tests:** 10 passed, lint passed, 100% requirements coverage
- **Result:** Review-ready MR created, .rpack signed and uploaded
- **Runtime:** ~50 seconds

---

## Tech Stack

- **AI:** Claude (Anthropic API) via GitLab Duo
- **Signing:** Ed25519 (pure Python, RFC 8032)
- **Hashing:** SHA-256 with canonical JSON serialization
- **Archiving:** Deterministic PAX-format TAR
- **CI/CD:** GitLab CI with Docker executor
- **Testing:** pytest + ruff
- **Language:** Python 3.11

---

## Links

- **Personal Project (live demos):** [gitlab.com/ryanjmichie1/ForgeProof](https://gitlab.com/ryanjmichie1/ForgeProof)
- **Hackathon Submission:** [gitlab-ai-hackathon/participants/35326234](https://gitlab.com/gitlab-ai-hackathon/participants/35326234)

---

*Built for the [GitLab Duo AI Hackathon](https://gitlab.devpost.com/) (Feb 9 - Mar 25, 2026)*
