# R0 baseline

Gate state is maintained in [implementation-status.md](implementation-status.md); this document records the reproducible foundation, not completion of R1. Source is the official Odoo Community 19 commit `5c7defb49e020fec8b6bb82403a2f54eb79e92e1` on local branch `platform/r1`. Official Git ancestry and `upstream` remote are retained. `upstream.lock` records provenance and the inspected subsequent upstream delta.

## Environment and isolation

- Windows PowerShell host; Git 2.56.0, uv 0.13.5, Docker Engine 29.9.2 and Compose 5.6.1.
- Container Python 3.12.16 and PostgreSQL 16.15; digest-pinned images and Dockerfile frontend in `deploy/runtime.lock.json`. Linux amd64; Python dependencies and build tools locked with hashes; OS packages from the recorded Debian snapshot.
- Docker reports 16 CPUs and 8,290,807,808 bytes memory following the user's resource increase. Limits: app 2 CPUs/1.5 GiB, DB 1 CPU/512 MiB, edge 0.5 CPU/128 MiB; maintenance runs separately with a 1.5 GiB limit. This is the actual setup, not an assertion of the provisional benchmark profile.
- App runs as UID/GID 10001; edge as 101. Read-only app code/root filesystem, writable named data volume and tmpfs. Separate config, bootstrap, DB and evidence volumes prevent app access to DB administration/bootstrap credentials.
- This Docker Desktop environment stalled on Windows host file bind mounts. Configuration is transferred over stdin into named volumes; backup artifacts use Docker cp. No Docker socket is mounted into app or maintenance containers.
- App and DB have only an internal network. Nginx has a second bridge for host access and publishes only `127.0.0.1:18069` (or a checked free port). Native database-manager routes are blocked at the edge; native `list_db=False` alone still renders that UI. No DB port is published.
- Cron is disabled during the foundation experiment. This is a disposable development profile, not a production deployment profile or the R1 executor.

## Fresh-checkout commands

Run from the repository root using the installed Python 3.12 interpreter, or use the following uv prefix. No global Python modification is required.

```powershell
uv run --no-project --python 3.12 tools/r0.py setup
uv run --no-project --python 3.12 tools/r0.py build
uv run --no-project --python 3.12 tools/r0.py bootstrap
uv run --no-project --python 3.12 tools/r0.py up
uv run --no-project --python 3.12 tools/r0.py http
uv run --no-project --python 3.12 tools/r0.py inspect
```

`setup` generates a project name, explicit disposable DB target, local credentials and a state file. Run setup serially and inspect its returned project/target before starting a separate checkout. Existing state is reused, not overwritten. The `bootstrap` guard refuses to initialize an existing DB; inspect a partial failure and select a new harness target rather than retrying blindly. Each command writes timestamped evidence without logging credential values.

The returned loopback URL serves the baseline. Login is `admin`; the generated password is available to the local operator in `.local/r0/bootstrap-password` and is never a shared default or a tracked file. Do not upload these credentials. At present the authenticated screen is the inherited Apps interface with catalog advertisements; it is not the planned neutral shell and does not imply ERP applications are installed.

Stop without deleting data:

```powershell
uv run --no-project --python 3.12 tools/r0.py down
```

There is deliberately no implicit reset/prune command. Unknown databases/volumes must not be deleted. All existing failed/recovery fixture targets are retained and identified in the local state and work log.

## Native lifecycle experiment

On a newly bootstrapped harness site, run the actions in this order. Each step must succeed except `fail`, whose intended migration failure is positively identified and treated as an expected test result, followed by an independent partial-commit check.

```powershell
uv run --no-project --python 3.12 tools/r0.py install
uv run --no-project --python 3.12 tools/r0.py upgrade
uv run --no-project --python 3.12 tools/r0.py up
uv run --no-project --python 3.12 tools/r0.py multiworker
uv run --no-project --python 3.12 tools/r0.py backup
uv run --no-project --python 3.12 tools/r0.py fail
uv run --no-project --python 3.12 tools/r0.py check-partial
uv run --no-project --python 3.12 tools/r0.py restore
uv run --no-project --python 3.12 tools/r0.py uninstall-restored
uv run --no-project --python 3.12 tools/r0.py reopen-restored
uv run --no-project --python 3.12 tools/r0.py up
uv run --no-project --python 3.12 tools/r0.py http
```

The fixtures are native development addons, not R1 `.mplug` packages. V1 creates a model, extension label and attachment; v2 adds schema and transforms extension data while preserving base values and attachment bytes. The failed v3 migration commits a recognizable change then raises. Old app/edge processes are stopped before mutation and backup; a new process confirms the committed change before restoration. Restore verifies DB/filestore hashes and the exact checkpoint image, restores into a new harness-owned DB and checks data/attachment reads offline. Native uninstall then removes the fixture model/table and its dependent extension. Reopening rotates restored password hashes/database secret and checks no technical API keys are present. These safety measures do not substitute for the independently journaled R1 control plane.

The multiworker probe creates a uniquely identified manual field in a maintenance process, signals registry changes, checks 80 responses through eight concurrent clients and requires at least two HTTP worker PIDs in logs. Its pending/committed/passed state prevents blind duplicate field creation after an interrupted test. A missing second PID is a failed coverage result, not permission to report synchronization passed.

Raw database dumps and filestore archives remain under ignored `.local/r0/backups` and a private evidence volume; only manifests/checksums and test observations are versioned. Keep the old runtime image ID recorded in checkpoint metadata; do not prune it while recovery remains required. This harness rejects a mismatched current runtime instead of pretending code downgrade is schema recovery.

## Independent reproduction

After the final baseline has no fixture modules installed and has been reopened through the harness:

```powershell
uv run --no-project --python 3.12 tools/r0_repro.py
```

This builds a second image without cache, compares runtime-source hashes and installed Python package versions, initializes another marked disposable DB from that image, compares exact installed-addon versions, and exercises distinct native registries/parameter values for both DBs. A reserved reproduction target must be reconciled before re-running. Build output bytes need not be identical across native wheel builds; the declared source/package inventories must be identical. Results and the current gate decision are in the verification/status records.

## Observed findings and limitations

The curated distribution needed one generated base category metadata seed because base catalog records refer to categories normally populated from excluded addon manifests. The optional HTML editor imports IAP/mail helpers outside its declared dependency list; it is not loaded. Two unchanged upstream contrast functions needed by web frontend SCSS are supplied by the small `mp_compat` addon through the supported asset registry. See the ADR and patch ledger. The strengthened HTTP probe rejects Odoo's compiler-error CSS even when the response status is 200; actual browser inspection caught that coupling.

The reference evidence includes styled login and authenticated web-client screenshots, real PostgreSQL lifecycle logs, hashes, image identities, dependency versions and resource samples. Session latency observations are a small warm local baseline, not the R1 Notes benchmark. No workspace authorization, neutral shell, custom page SDK, public service registry, package solver, durable jobs/outbox or production executor is claimed complete at R0.
