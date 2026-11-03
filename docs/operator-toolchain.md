# Selected local operator toolchain

`deploy/host-toolchain.lock.json` records the selected Windows interpreter,
Node/npm/TypeScript versions and dependency locks. The current operator uses
Python3.12.16 at `.local/toolchain/operator-python16/Scripts/python.exe`.
Use that explicit interpreter for subsequent operator commands and evidence.
The earlier `.venv` remains a Python3.12.15 checkpoint, not the selected tooling.

For a new environment, from the project root with an existing trusted uv:

```powershell
$toolchainUv = (Get-Command uv -ErrorAction Stop).Source
$toolchainLock = Get-Content deploy/host-toolchain.lock.json -Raw | ConvertFrom-Json
& $toolchainUv python install --install-dir .local/toolchain/python16 --no-bin --no-registry --python-downloads-json-url $toolchainLock.python_provenance.metadata_url 3.12.16
& $toolchainUv venv --python .local/toolchain/python16/cpython-3.12.16-windows-x86_64-none/python.exe --no-python-downloads .local/toolchain/operator-python16
& $toolchainUv pip install --python .local/toolchain/operator-python16/Scripts/python.exe --require-hashes --only-binary :all: -r deploy/requirements-tooling.lock -r deploy/requirements-operator.lock
```

The metadata URL is pinned to an official Astral source commit; its metadata
and exact interpreter archive SHA-256 are recorded in the lock. This works with
the existing uv version without self-updating it or changing global Python,
PATH, Windows registry, shared interpreter installations or the old environment.
Use new paths for a future candidate rather than overwriting a working toolchain.

The selected environment passed232 affected operator checks, TypeScript,
all101 unchanged frozen files/eight rows, and read/sign/verify with existing
RSA keys. All13 locked package versions are unchanged. See
`docs/evidence/G7/20261104-operator-python16-01/runtime-qualification.json`.
Application/worker images remain separate; native-library advisory and full
release qualification are still required by G7.
