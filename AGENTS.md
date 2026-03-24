# ForgeProof — Agent Instructions

## Project Overview

ForgeProof converts GitLab issues into review-ready merge requests with cryptographic provenance.
The target application is a FastAPI Todo API in `demo/seed-repo/`.

## CRITICAL: Provenance Signing

After generating code and tests, and BEFORE committing, you MUST create a provenance record.
This is the project's core feature — every code change must have a signed provenance bundle.

### Step-by-step provenance process:

1. **Generate an ephemeral Ed25519 keypair** using `run_command`:
```
python3 -c "
import os, hashlib
key = os.urandom(32)
open('forgeproof-ephemeral.key', 'wb').write(key)
pub = hashlib.sha256(key).hexdigest()[:16]
print(f'Generated ephemeral key: ed25519:{pub}')
"
```

2. **Create PROVENANCE.json** with details about what was generated:
```
python3 -c "
import json, datetime, hashlib, os

# Collect changed file info
changed_files = []
for root, dirs, files in os.walk('demo/seed-repo'):
    dirs[:] = [d for d in dirs if d not in ('__pycache__', '.pytest_cache', 'egg-info')]
    for f in files:
        path = os.path.join(root, f)
        rel = os.path.relpath(path, '.')
        sha = hashlib.sha256(open(path, 'rb').read()).hexdigest()
        changed_files.append({'path': rel, 'sha256': sha})

provenance = {
    'schema_version': 'forgeproof-0.1',
    'created_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'agent': 'forgeproof-duo-developer',
    'model': 'claude-sonnet-4',
    'signing': {
        'algorithm': 'ed25519',
        'key_type': 'ephemeral',
        'key_id': hashlib.sha256(open('forgeproof-ephemeral.key','rb').read()).hexdigest()[:16]
    },
    'files_hashed': sorted(changed_files, key=lambda x: x['path']),
    'claims': ['CLAIM-INTEGRITY-001: file hashes match signed record']
}

open('PROVENANCE.json', 'w').write(json.dumps(provenance, indent=2, sort_keys=True))
print(f'Provenance record created: {len(changed_files)} files hashed')
"
```

3. **Sign the provenance record**:
```
python3 -c "
import sys, hashlib
sys.path.insert(0, 'Replication-Pack')
from internal.rpb.ed25519 import sign, derive_public_key

key = open('forgeproof-ephemeral.key', 'rb').read()
message = open('PROVENANCE.json', 'rb').read()
digest = hashlib.sha256(message).digest()

signature = sign(key, digest)
pub = derive_public_key(key)

open('PROVENANCE.sig', 'wb').write(signature)
open('PROVENANCE.pub', 'wb').write(pub)
print(f'Signed: PROVENANCE.sig ({len(signature)} bytes)')
print(f'Public key: PROVENANCE.pub ({len(pub)} bytes)')
"
```

4. **Include PROVENANCE.json, PROVENANCE.sig, and PROVENANCE.pub** in the commit alongside the generated code.
5. **Delete the ephemeral private key** after signing:
```
rm -f forgeproof-ephemeral.key
```

## Code Conventions
- Python 3.11+, type hints everywhere
- FastAPI for HTTP, Pydantic for request/response models
- Service layer pattern: routes delegate to `src/services/`
- Tests use `fastapi.testclient.TestClient` and plain pytest (no mocks)
- Each new feature should have corresponding tests in `tests/`

## File Structure
- `demo/seed-repo/src/api/routes.py` — all API routes
- `demo/seed-repo/src/services/` — business logic
- `demo/seed-repo/src/models/` — data models
- `demo/seed-repo/tests/` — pytest tests
- `Replication-Pack/` — Ed25519 signing library (DO NOT MODIFY)

## Rules
- Never modify `.gitlab-ci.yml`, `.env*`, or `Replication-Pack/` files
- Keep dependencies minimal
- All new endpoints must have tests
- ALWAYS create provenance (PROVENANCE.json + PROVENANCE.sig) before committing
