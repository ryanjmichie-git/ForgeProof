param(
    [string]$KeyPath = "devkey.ed25519",
    [string]$PackPath = "demo.rpack"
)

if (-not (Test-Path $KeyPath)) {
    python -c "import os; open('$KeyPath','wb').write(os.urandom(32))"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

python cmd/rpb.py pack examples/complete-demo --output $PackPath --sign-key $KeyPath --tests "python -m unittest"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python cmd/rpb.py verify $PackPath --pubkey $KeyPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python cmd/rpb.py verify $PackPath --pubkey $KeyPath --recheck
exit $LASTEXITCODE

