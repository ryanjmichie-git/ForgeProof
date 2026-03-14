#!/usr/bin/env bash
set -euo pipefail

PACK_DIR="${1:-.}"

echo "[1/3] Verifying hashes..."
# placeholder: call rpb verify --offline --dir "$PACK_DIR"
echo "TODO: rpb verify --offline --dir \"$PACK_DIR\""

echo "[2/3] Verifying signature..."
echo "TODO: rpb verify --sig --dir \"$PACK_DIR\""

echo "[3/3] Verifying policy compliance..."
echo "TODO: rpb verify --policy --dir \"$PACK_DIR\""

echo "OK (stub). Use 'rpb verify <pack.rpack>' for real verification."