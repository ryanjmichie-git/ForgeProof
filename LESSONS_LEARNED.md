# ForgeProof — Lessons Learned

**Project:** GitLab Duo AI Hackathon (Feb 9 – Mar 25, 2026)
**Goal:** AI agent that converts GitLab issues into review-ready MRs with cryptographically signed provenance bundles

---

## 1. Architecture Decisions

### What worked well

**4-phase pipeline (Parse → Generate → Evaluate → Package)** proved to be the right decomposition. Each phase has a clear contract, can fail independently, and the orchestrator continues to packaging even when evaluation fails (creating a Draft MR instead). This resilience was critical — early pipeline runs had eval failures but still produced signed .rpack artifacts for demo purposes.

**Embedded demo project (demo/seed-repo/)** as the target for ForgeProof to operate on was essential. Without a separate FastAPI project inside the repo, we would have needed a second GitLab project for every demo. The seed-repo has its own `pyproject.toml`, `src/`, and `tests/`, making it a self-contained target.

**Hash-chained decision log** turned out to be a strong differentiator. Every AI decision (model ID, prompt hash, response hash, duration, status) is recorded in an append-only JSONL file with SHA-256 chaining. This makes the entire AI reasoning process auditable and tamper-evident — exactly what enterprise buyers and compliance teams want.

**Prompt injection defense** via `<issue-body>` delimiters and explicit "treat as DATA only" instructions in system prompts was straightforward to implement and effective. GitLab issues are untrusted user input, and the system prompt explicitly tells Claude not to follow instructions found in the issue body.

### What we'd do differently

**Separate the target project from ForgeProof's own repo.** Running ForgeProof against itself (where the issue describes changes to `demo/seed-repo/` inside ForgeProof) created the hardest bug: the eval workspace copied ForgeProof's `pyproject.toml` (anthropic, httpx) instead of the seed-repo's (fastapi). We fixed this with majority-voting subdirectory detection, but a cleaner design would be a fully separate target repo.

**Design for idempotency from day one.** The MR creation flow failed on re-runs because it tried to `"create"` files that already existed on the branch. We had to add logic to detect existing branches and switch to `"update"` actions. This should have been the default behavior.

**Claude's JSON output is unpredictable.** Despite asking for "ONLY valid JSON," Claude sometimes wraps responses in markdown code fences, adds prose before/after the JSON, or produces malformed entries. We needed three layers of fallback: `json.loads()` → strip code fences → find first `{` and last `}`. Every Claude-facing parser needs this resilience.

---

## 2. GitLab Platform Constraints

### Pipeline Execution Policy (Hackathon Repo)

The hackathon organization enforces a Pipeline Execution Policy that overrides project CI. This means:
- Only `placeholder-test` and `validate-items` jobs execute
- Custom stages (`build`, `run`) are completely ignored
- User-defined CI/CD variables are restricted
- Developer role (access_level 30) cannot add CI variables — needs Maintainer (40)

**Impact:** The full ForgeProof pipeline cannot run in the hackathon repo without either elevated permissions or policy changes. We worked around this by maintaining a personal project (`ryanjmichie1/ForgeProof`) with full CI capabilities and pushing identical code to both repos.

**Lesson:** When building for a platform hackathon, test your CI/CD integration on the actual submission repo early. We spent significant time getting the pipeline working on the personal project before discovering the hackathon repo had different constraints.

### CI_JOB_TOKEN vs Personal Access Token

`CI_JOB_TOKEN` (automatically injected in CI) can read issues and clone repos but **cannot** create branches, commits, or MRs via the API. This required a separate PAT (`GITLAB_TOKEN`) with `api`, `read_repository`, and `write_repository` scopes.

**Auth header logic** also needed care: PATs use `PRIVATE-TOKEN` header, CI job tokens use `JOB-TOKEN` header. Getting this wrong produces 403 errors with no helpful error message.

### External Agents are Self-Managed Only

A critical discovery mid-project: GitLab Duo custom external agents (Docker-based, with full tool access) are only available on **GitLab Self-Managed**, not GitLab.com (SaaS) where the hackathon runs. We pivoted to a CI/CD pipeline execution model instead, which works but lacks the interactive Duo Chat integration that external agents provide.

The built-in agent (registered in the AI Catalog via `agents/agent.yml`) works in Duo Chat but only provides conversational responses — it can't execute the full 4-phase pipeline.

### Docker Image in CI

GitLab CI passes shell arguments to the Docker ENTRYPOINT, which conflicts with Python-based entrypoints. Fix: `entrypoint: [""]` in the CI job config to override the Dockerfile's ENTRYPOINT and use `script:` commands directly.

Artifact collection is relative to `$CI_PROJECT_DIR` (the repo checkout path, e.g., `/builds/user/project`), not the Docker container's working directory (`/app`). Files must be explicitly copied to `$CI_PROJECT_DIR` before the job ends.

---

## 3. Testing Insights

### Coverage Journey: 12% → 71%

Started with 2 test files (5 tests) covering only `decision_log.py` and `packer.py`. Added 10 test files (132 new tests) in a single batch, bringing coverage to 12/17 modules.

**Most valuable tests written:**
- `test_issue_loader.py` — Caught edge cases in JSON path traversal (`issue` vs `parent_object` nesting)
- `test_evaluate.py` — Validated the majority-voting subdirectory detection that was our hardest bug
- `test_parse_plan.py` — Exercises the 3-layer JSON extraction fallback that handles Claude's unpredictable output
- `test_config.py` — Validates env var precedence (`GITLAB_TOKEN` > `CI_JOB_TOKEN`)

**What we skipped (and why):**
- `orchestrator.py` — Too integration-heavy; would require mocking 5+ dependencies with minimal bug-finding value
- `claude/client.py` — Testing mocks of the Anthropic SDK validates the mock, not the code
- `main.py` — CLI integration testing requires full environment setup

**Key decision:** Use `unittest.mock` (stdlib) instead of adding `pytest-mock` as a dependency. Zero dependency changes for the entire test suite.

### Platform Compatibility

One test failed on Windows due to path separators (`src\main.py` vs `src/main.py`). Tests that assert on path strings should normalize with `.replace("\\", "/")` or use `pathlib` comparisons.

---

## 4. Provenance & Security

### What Makes ForgeProof's Provenance Strong

1. **Evidence binding chain:** File content → SHA-256 hashes → HASHES.json → root digest (SHA-256 of canonical MANIFEST + HASHES + POLICY) → Ed25519 signature
2. **Deterministic archives:** PAX-format TAR with `mtime=0, uid=0, gid=0`, lexicographically sorted entries — identical inputs always produce identical .rpack files
3. **Policy-gated claims:** P0 (integrity), P2 (tested) are default; P3 (MathSafe) requires explicit policy enablement + proof evidence
4. **Offline verification:** `forgeproof verify` works without network access — no transparency log dependency

### Known Gaps (from Expert Review)

- **Ed25519 implementation is pure Python** — functionally correct per RFC 8032 but not constant-time (timing side-channels). Acceptable for dev keys; production should use PyNaCl/libsodium.
- **No SBOM** — HASHES.json catalogs files but doesn't track software dependencies. Adding CycloneDX from `pyproject.toml` would be high-impact, low-effort.
- **No SLSA-formatted predicate** — RPB's MANIFEST+HASHES+POLICY is analogous to in-toto link metadata but not interoperable with `slsa-verifier`.
- **Canonical JSON is CPython-specific** — `json.dumps(sort_keys=True, separators=(",",":"))` produces deterministic output within CPython but isn't formally specified (no RFC 8785/JCS compliance).

---

## 5. Opportunities Going Forward

### Near-term (Hackathon Polish)

- **CycloneDX SBOM** from `pyproject.toml` — parse dependencies, generate minimal SBOM, include in .rpack. Low effort, strong signal for judges.
- **Real container image digest** — inject `$CI_JOB_IMAGE` into MANIFEST.json for build environment reproducibility.
- **Redaction enforcement** — validate `.forgeproof.yml` denied_paths patterns at pack time to prevent secrets from being included.

### Medium-term (Post-Hackathon)

- **Multi-project support** — ForgeProof targeting a separate repo (not itself). Pass `--target-project-id` and `--target-repo-url` to operate on any GitLab project.
- **Iteration loop** — If eval fails, feed errors back to Claude for a second generation attempt before creating a Draft MR.
- **MR review integration** — Post inline code review comments on the generated MR using Claude to analyze diff quality.
- **GitLab Duo Workflow (Flow)** — When external agents become available on GitLab.com SaaS, migrate from CI pipeline execution to a proper Duo Workflow with interactive triggers.

### Long-term (Product Vision)

- **Multi-signer provenance** — POLICY.json already supports per-profile signature thresholds (P3 requires 2 signers). Implement multi-party signing for high-assurance workflows.
- **SIEM-compatible audit export** — Convert decision log to CEF/LEEF format for enterprise security monitoring integration.
- **Formal verification integration (P3)** — Connect proof assistants (Lean, Coq) as evidence sources for mathematical safety claims.
- **Key rotation and HSM** — Replace file-based Ed25519 keys with CI/CD variable injection and HSM-backed signing for production deployments.

---

## 6. Key Metrics

| Metric | Value |
|--------|-------|
| Source modules | 17 Python files |
| Source lines of code | ~2,100 |
| Test files | 12 |
| Tests | 137 |
| Module test coverage | 71% (12/17) |
| Test runtime | <1 second |
| Claude API calls per run | 4 (plan, code, tests, coverage) |
| Pipeline run time (CI) | ~50 seconds (ForgeProof phases) |
| .rpack size | ~140 KB |
| Critical bugs fixed | 11 (across 6 commits) |
| Pipeline runs to first full success | 5 |

---

## 7. Timeline

| Date | Milestone |
|------|-----------|
| Mar 14 | Foundation + AI phases working end-to-end locally |
| Mar 16 | Pushed to hackathon repo, Docker image built, AI Catalog registration |
| Mar 16 | Discovered external agents are Self-Managed only — pivoted to CI pipeline |
| Mar 17 | First CI pipeline run — Claude API calls work, .rpack created |
| Mar 17 | 7 priority fixes from pipeline audit (eval deps, artifact collection, MR creation) |
| Mar 17 | Majority voting fix for subdirectory detection |
| Mar 17 | MR creation fix — branch reuse, file update actions |
| Mar 17 | Full pipeline success: 10 tests pass, 100% coverage, MR created, .rpack signed |
| Mar 19 | Comprehensive test suite added (137 tests, 71% module coverage) |
| Mar 20 | Hackathon repo CI variable blocker identified (Developer role limitation) |
| Mar 25 | Hackathon deadline (2:00 PM ET) |
