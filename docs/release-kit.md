# Local R1 release kit rehearsal

G7 is in progress. The kit remains a draft until its operator setup and clean
application installation are actually qualified. [Status](implementation-status.md)
is authoritative; [ADR0053](architecture-decisions/0053-local-release-kit.md)
defines the artifact and trust boundaries.

The producer uses the selected Python3.12.16 operator, a committed source tree,
the exact qualified local images and an independently selected catalog/trust
file. For the current disposable qualification, create one fresh destination:

```powershell
.local/toolchain/operator-python16/Scripts/python.exe -X utf8 release/assemble.py --output .local/releases/r1-0.1.23 --catalog .local/g7-fresh-release-01/target21/operator/catalog --trust .local/g7-fresh-release-01/target21/operator/trust.json --receipt docs/evidence/G7/20261104-release-kit-01/assembly.json
```

The producer refuses an existing destination and records its phase/components.
On failure, inspect that record and the actual process/diagnostic before any
continuation. Do not rerun it hoping an existing partial directory will work.
No live application data or executor authority is copied. Native plugins and
same-origin pages are trusted; reference digest curation never grants execution
approval.

Once assembled, verify the kit before consuming its files:

```powershell
python release/verify.py .local/releases/r1-0.1.23
python .local/releases/r1-0.1.23/scripts/setup_operator.py .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
```

The initial `python` needs a trusted Python3.12-or-newer installation only for
standard-library verification/extraction. The selected Windows interpreter and
hash-locked binary wheels then create a fresh project-local operator without
global Python/PATH/registry changes or runtime pip dependencies. The SDK creates
and verifies a new `private` child for control/configuration/authority data.
The public source/toolchain workspace is separate; the SDK never resets an
existing directory's ACL. Existing workdirs are refused.

Checksums detect corruption against an operator-selected trusted inventory;
they do not authenticate a publisher against an attacker replacing the entire
kit. The source ZIP records its Git commit. Follow the documented native
code/permission review when importing reference archives into a new catalog.

For a new operator workspace, the trusted reference initializer creates one new
loopback-only disposable realm. Use the interpreter and source paths recorded
in its `operator-setup.json`; these examples use the default rehearsal paths:

```powershell
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/initialize_reference.py prepare --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal --reference-fixture --port 18100
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/initialize_reference.py initialize --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/initialize_reference.py install --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/check_reference.py --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
```

Run each phase once, sequentially. Preparation verifies/loads the five exact
images, reserves new named networks/volumes and creates fresh private credentials
and scoped operator authority. `--reference-fixture` explicitly enables unattended
exact-hash approval only for this new disposable realm. Core initialization uses
an empty database; reference plugins then use ordinary independent
register/approve/apply, including native-code and permission acknowledgments.
The walkthrough creates only two Notes and one one-card Canvas board. Standard
record screens use native Odoo list/form descriptors.

`private/reference/state.json`, `logs/`, `operator/control/` and
`reference-checks.json` record the exact phase, diagnostics, independent journal
and minimal effects. A failure does not authorize replay: inspect the process,
Docker child, marker, database and journal before choosing a narrow continuation.
Never delete the workdir or rerun initialization against its existing database.
Passwords remain in the protected `private/reference/account-passwords.json`;
they are neither printed nor included in this public-input kit. Do not copy an
existing operator journal/issuer into a new installation.

The current rehearsal has actually reached `references_installed` from the kit
operator and committed initializer: three native reference plugins, six workspace
activations, distinct fresh credentials and a new independent control store.
The HTTP walkthrough has now passed five checks with two Notes/one board;
[backend qualification](evidence/G7/20261104-release-kit-01/application-bootstrap.json)
records the actual source overlays and narrow pre-data DNS continuation. Worker
integration passed subsequently below; twelve-case operational handoff is open.
No full G7 claim follows from these commands.

The worker is a separate operator action, after that backend walkthrough:

```powershell
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/initialize_worker.py --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
```

This once-only helper has passed its initial qualification. It starts the
locked reference Compose worker on the existing internal network, provisions
new scoped keys and two dedicated volumes, then independently reviews/publishes
the exact authority hash. It does not install metadata or select a connector;
the following separate integration steps follow once, in order:

```powershell
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/connect_worker.py register --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/connect_worker.py connect --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/connect_worker.py job --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
```

These three integration steps have passed the backend rehearsal. Registration
uses exact curated metadata, endpoint health and independent capability review;
the connector installs through normal native lifecycle approval. The job checks
saved revision and statistics under a fresh Alice session. Worker runtime must
remain identical. The helper records each phase before acting. Its state is in
`private/reference/worker/integration.json`. Worker provisioning phase is in
`private/reference/worker/state.json`; never replay an uncertain publication.

The actual final realm has five site installations/eight workspace activations,
two Notes, one board and one completed original-actor analysis job. Three lifecycle
operations completed under independent approval; the worker's original runtime
and publication stayed exact. [Integration evidence](evidence/G7/20261104-release-kit-01/worker-integration.json)
also verifies raw Notes rows against the actual pre-registration checkpoint.
Twenty-nine successful temporary helpers/replaced apps were retired; the four
current services and required storage/checkpoints remain.

A second empty host-only workspace also passed the full corrected offline
bootstrap command: [qualification](evidence/G7/20261104-release-kit-01/full-bootstrap-qualified.json).
It verified all thirteen selected packages and all374qualified application build
inputs, without creating a site or Docker assets. This closes the earlier
full-command-unexecuted limitation while preserving the first diagnosed record.

The twelve required procedures are in [operator runbooks](operator-runbooks.md).
[CLI/retained evidence cross-check](evidence/G7/20261104-release-kit-01/runbook-cross-check.json)
and [complete artifact privacy/source binding](evidence/G7/20261104-release-kit-01/kit-qualified.json)
have passed. The latter covers expanded/nested archives and image layers, all
54,196 source files against Git, and 133 known secret values. Eight exact upstream
documentation examples/compiled equivalents were reviewed individually.

The qualified kit source snapshot is `5456abf4`; later audit receipts are linked
from the repository evidence index, not claimed to be inside that earlier ZIP.
The kit remains a draft until browser/network, performance, accessibility and
the final G7/section28 operator/developer handoff pass. No full R1 claim is made.
