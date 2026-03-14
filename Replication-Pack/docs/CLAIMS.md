# Claims Semantics

## P0: Integrity

P0 means the pack content is internally consistent and verifiable:

- Hashes in `HASHES.json` match packaged files.
- Root digest is recomputed from canonical `MANIFEST.json`, `HASHES.json`, and `POLICY.json`.
- Required signature threshold for claimed profile is satisfied.

P0 does not prove functional correctness or absence of bugs.

## P2: Tested

P2 means declared test commands were executed and evidence was recorded:

- `commands.tests[]` includes executed commands.
- `evidence[]` contains `type="tests"` entries with `exit_code=0`.
- `EVIDENCE/TESTS/` contains captured stdout/stderr files.
- Policy requirements for P2 are satisfied.

P2 indicates tests passed in the recorded environment; it does not prove complete correctness.

## P3: MathSafe (Future/Policy-Gated)

P3 is policy-gated and disabled by default in MVP policy.
To claim P3, policy must explicitly enable it and require:

- proof commands,
- proof evidence,
- specification/property references as defined by policy.

Without those conditions, P3 claims are rejected during verify.

## What RPB Does Not Guarantee

- No guarantee that tests are exhaustive.
- No guarantee that runtime environments are identical across machines.
- No guarantee that source code is free of vulnerabilities.
- No guarantee of long-term key security if private keys are mishandled.
