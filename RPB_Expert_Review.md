# Replication-Pack (.rpack) — Expert Review Report

**Date:** 2026-03-14 | **Subject:** RPB v0.1.0 provenance bundle format | **Project:** ForgeProof

---

## 1. Cryptography Engineer Review

**Scope:** Ed25519 signing, hash integrity, deterministic serialization, threat model.

**Signing Implementation** — RPB uses a pure-Python Ed25519 implementation (`Replication-Pack/internal/rpb/ed25519.py`, 139 lines) following RFC 8032. `sign()`, `verify()`, and `derive_public_key()` are functionally correct but **not constant-time** — Python's arbitrary-precision integers and branching arithmetic create timing side-channels. This is acceptable for an MVP where the signing key is a dev key, but production deployments must swap to `PyNaCl` or the `cryptography` library backed by OpenSSL/libsodium.

**Root Digest Construction** — The root digest (`Replication-Pack/internal/root_digest.py`) is `sha256(canon(MANIFEST) || canon(HASHES) || canon(POLICY))`. This is sound: concatenation order is fixed, inputs are canonical JSON bytes, and SHA-256 outputs are fixed-length (no length-extension ambiguity). The digest binds all three metadata files into a single signed commitment.

**Canonical JSON** — `Replication-Pack/internal/canon.py` uses `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False, allow_nan=False)`. This produces deterministic output within CPython but is not a formal spec (no RFC 8785 / JCS compliance). **Risk:** float serialization edge cases (`1.0` vs `1`) could theoretically break cross-implementation verification. Recommendation: document the canonical form explicitly or adopt JCS (RFC 8785).

**Deterministic TAR** — `Replication-Pack/internal/rpb/pack_writer.py` creates PAX-format archives with `mtime=0, uid=0, gid=0, uname="", gname=""` and lexicographically sorted entries. This eliminates OS-dependent variation. Minor risk: PAX extended headers may vary across Python versions — pin the Python version in the Dockerfile.

**Key Management** — Keys are raw 32-byte Ed25519 seeds stored as files. No rotation, no revocation, no HSM integration. The dev key checked into the repo is appropriate for the hackathon; production requires CI/CD variable injection and a key rotation strategy.

**Hash Agility** — SHA-256 is hardcoded throughout, but `HASHES.json` declares `"hash_algo": "sha256"`, providing a migration path. No active algorithm negotiation exists. Acceptable for MVP.

**Multi-Signer** — `POLICY.json` supports per-profile signature thresholds (P3 requires 2 signers). The infrastructure exists in `Replication-Pack/internal/rpb/verify_signatures.py` but only single-signer flows are exercised and tested.

---

## 2. Supply Chain Security Specialist Review

**Scope:** SLSA provenance, SBOM, attestation standards, build environment capture.

**SLSA Alignment** — RPB's P0–P3 profiles map loosely to SLSA levels: P0 ≈ SLSA L1 (integrity), P2 ≈ SLSA L2 (build + test evidence with signed provenance). However, RPB does **not** emit a formal SLSA provenance predicate (`slsa_provenance_v1`). For interoperability with tools like `slsa-verifier`, recommend adding an optional SLSA-formatted provenance artifact inside the pack.

**SBOM** — **Not implemented.** No CycloneDX or SPDX output. `HASHES.json` catalogs files by path and hash but does not track software dependencies, component licenses, or vulnerability metadata. Recommendation: generate a minimal CycloneDX SBOM from `pyproject.toml` and include it as a pack artifact. Low effort, high signal for judges.

**Attestation Standards Comparison:**
- **vs. in-toto:** RPB's MANIFEST+HASHES+POLICY is analogous to in-toto link metadata. RPB lacks layout files (expected supply chain steps), making it simpler but less expressive. No functionary abstraction.
- **vs. Sigstore:** RPB is offline-first by design — no transparency log, no OIDC identity binding. This is a deliberate trade-off: air-gapped verification without network dependencies. The cost is no third-party auditability of signing events.

**Build Environment** — MANIFEST captures `environment.image_digest`, `os_arch`, and `toolchain[]` (`Replication-Pack/schemas/MANIFEST.json`). ForgeProof currently writes a placeholder image digest (`sha256:000...`) — this needs real container digest injection in the CI pipeline.

**Evidence Binding** — Strong. Test stdout/stderr files in `EVIDENCE/TESTS/` are individually hashed in `HASHES.json`, which feeds into the root digest, which is signed. Any post-signing modification of evidence is detectable. Evidence entries in MANIFEST include `exit_code`, command, and timestamps.

**Redaction** — MANIFEST declares `redactions[]` with glob patterns and reasons (e.g., `.env`, `**/*_key*`). However, these are **advisory only** — no runtime enforcement prevents secrets from being included in the pack. Recommendation: add a pre-pack validation step that rejects files matching redaction patterns.

---

## 3. Compliance / GRC Analyst Review

**Scope:** Audit evidence, regulatory framework mapping, change traceability.

**Change Traceability** — The hash-chained decision log (`src/forgeproof/provenance/decision_log.py`) provides strong audit evidence. Each JSONL entry contains `seq`, `timestamp`, `phase`, `model_id`, `decision_summary`, `prev_hash`, and `entry_hash`. The chain is verifiable via `DecisionLog.verify_chain()`. This satisfies **SOC 2 CC8.1** (changes are authorized and documented) — an auditor can independently verify the chain and reconstruct the full decision sequence from issue through code generation to evaluation.

**SOC 2 Mapping:**
- **CC6.1 (Logical Access):** Partially met. Signing key identity provides attribution, but no access control enforcement. The pack proves *who signed*, not *who was authorized to sign*.
- **CC7.2 (System Monitoring):** No real-time monitoring. Post-hoc verification via `rpb verify` provides after-the-fact assurance. Sufficient for batch audit but not continuous compliance.
- **CC8.1 (Change Management):** Well-served. Decision log + signed pack + evaluation scorecard provide complete change documentation.

**FedRAMP Mapping:**
- **CM-3 (Configuration Change Control):** Decision log with hash chain maps directly. Each AI-generated change is logged with inputs, outputs, and rationale.
- **SI-7 (Software & Information Integrity):** Ed25519 signature verification maps directly. `rpb verify` provides deterministic integrity checking. **Gap:** No SIEM-compatible log format (e.g., CEF, LEEF) for automated compliance monitoring.

**Independent Verification** — `rpb verify` (`Replication-Pack/internal/rpb/verify_signatures.py`) is auditor-friendly: offline, deterministic, produces JSON output, and uses clear exit codes (0=pass, 2=sig invalid, 3=hash mismatch, 4=policy violation, 5=recheck failed). The `--recheck` flag re-runs tests from pack evidence, enabling reproducibility verification.

**Policy Enforcement** — P0–P3 profiles with configurable requirements (`must_include_paths`, `must_have_commands`, `must_have_evidence_types`). P3 is disabled by default, preventing over-claiming. **Gap:** No policy approval workflow — policy changes are unaudited. No policy version history.

**Evidence Completeness** — All AI interactions (prompts, responses) are captured with SHA-256 hashes and included in the signed pack. Test output, evaluation scorecard, issue snapshot, implementation plan, and git metadata are all present. An auditor can reconstruct the complete chain: issue → plan → code → tests → evaluation → signed bundle.

---

## Priority Improvements (Top 5)

| # | Improvement | Perspective | Effort | Impact |
|---|------------|-------------|--------|--------|
| 1 | **Enforce redaction patterns at pack time** — reject files matching `redactions[]` before signing | Supply Chain | Low (add validation in `staging.py`) | Prevents secret leakage into packs |
| 2 | **Inject real container image digest** into MANIFEST `environment.image_digest` | Supply Chain | Low (read `$CI_JOB_IMAGE` in Dockerfile) | Pins build environment for reproducibility |
| 3 | **Add minimal CycloneDX SBOM** from `pyproject.toml` as pack artifact | Supply Chain | Medium (new utility, ~50 lines) | SBOM checkbox for judges + enterprise appeal |
| 4 | **Document canonical JSON spec** explicitly (or adopt JCS/RFC 8785) | Crypto | Low (documentation) | Cross-implementation verification safety |
| 5 | **Add SIEM-compatible log export** (JSON lines with standard fields) for decision log | Compliance | Medium (format adapter) | FedRAMP CM-3 automation readiness |

*Items 1–2 are achievable before hackathon deadline. Items 3–5 are strong differentiators if time permits.*
