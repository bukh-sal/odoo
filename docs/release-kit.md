# Local R1 release kit rehearsal

G7 is in progress. The selected local draft is `.local/releases/r1-0.1.26`.
Its clean offline operator, fresh application and separate worker passed backend
qualification. The fresh browser walkthrough and final audit are pending.
[Status](implementation-status.md) tracks closure.
[ADR0053](architecture-decisions/0053-local-release-kit.md) defines the artifact
and trust boundaries.

The producer uses the selected Python3.12.16 operator, a committed source tree,
the exact qualified local images and an independently selected catalog/trust
file. For the current disposable qualification, create one fresh destination:

```powershell
.local/toolchain/operator-python16/Scripts/python.exe -X utf8 release/assemble.py --output .local/releases/r1-final --catalog <operator-selected-catalog> --trust <operator-selected-trust.json> --application-build <qualified-candidate-build.json> --application-reproduction <passed-reproduction.json> --receipt <fresh-assembly-receipt.json>
```

The producer refuses an existing destination and records its phase/components.
On failure, inspect that record and the actual process/diagnostic before any
continuation. Do not rerun it hoping an existing partial directory will work.
No live application data or executor authority is copied. Native plugins and
same-origin pages are trusted; reference digest curation never grants execution
approval.

The producer now requires explicit matching build/reproduction evidence and
current build-source hashes ([ADR0058](architecture-decisions/0058-explicit-release-application-inputs.md)).
Replace every angle-bracket placeholder with independently selected actual paths;
the command above describes the final producer, not an executed final assembly.
The earlier `r1-0.1.23` draft retains its dated qualification scope.
Source-only `refresh_draft.py` likewise requires both receipt
options and refuses an image/base/inventory mismatch. It cannot update an old
kit's application image by refreshing source alone. Do not rerun assembly against
the existing draft or reuse its old receipts to conceal changed application inputs.

Once assembled, verify the kit before consuming its files:

```powershell
$kit = '.local/releases/r1-0.1.26'
$work = '.local/release-kit-new-operator'
python release/verify.py $kit
python "$kit/scripts/setup_operator.py" $kit --workdir $work
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
in its `operator-setup.json`. The examples below use the new workdir above.

After reviewing the reference packages and exact digests, import them into the
new private catalog before initializing the application. These commands use the
kit's operator interpreter and the ordinary catalog CLI.

```powershell
$operator = "$work/operator/Scripts/python.exe"
$index = Get-Content "$kit/plugins/index.json" -Raw | ConvertFrom-Json
foreach ($artifact in $index.packages) {
    & $operator -I "$work/source/tools/modular.py" --config "$kit/plugins/curated-trust.json" catalog --store "$work/private/catalog" add "$kit/$($artifact.file)" --digest $artifact.digest
    if ($LASTEXITCODE -ne 0) { throw 'Catalog import failed. Inspect the private catalog and diagnostic.' }
}
```

```powershell
$port = 18102  # Select an unused loopback port.
$initializer = "$work/source/release/initialize_reference.py"
& $operator -I $initializer prepare --kit $kit --workdir $work --reference-fixture --port $port
& $operator -I $initializer initialize --kit $kit --workdir $work
& $operator -I $initializer install --kit $kit --workdir $work
& $operator -I "$work/source/release/check_reference.py" --kit $kit --workdir $work
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

The fresh core26 rehearsal installed three native reference plugins across six
workspace activations. Its five HTTP checks covered distinct sessions, native
Notes list/form descriptors, denied cross-workspace access, the Labels extension
and a minimal Canvas board. During the first fresh initialization the catalog
import was missing from this guide. The corrected initializer checks the entire
kit catalog before starting the database. The rehearsal imported the reviewed
digests and resumed publication from the recorded empty-install state.
[Backend qualification](evidence/G7/20261105-core26-release-kit-01/fresh-backend.json)
and [catalog reconciliation](evidence/G7/20261105-core26-release-kit-01/catalog-and-publication-reconciliation.json)
record the actual scope.

The worker is a separate operator action, after that backend walkthrough:

```powershell
& $operator -I "$work/source/release/initialize_worker.py" --kit $kit --workdir $work
```

This once-only helper has passed its initial qualification. It starts the
locked reference Compose worker on the existing internal network, provisions
new scoped keys and two dedicated volumes, then independently reviews/publishes
the exact authority hash. It does not install metadata or select a connector;
the following separate integration steps follow once, in order:

```powershell
$connector = "$work/source/release/connect_worker.py"
& $operator -I $connector register --kit $kit --workdir $work
& $operator -I $connector connect --kit $kit --workdir $work
& $operator -I $connector job --kit $kit --workdir $work
```

These three integration steps have passed the backend rehearsal. Registration
uses exact curated metadata, endpoint health and independent capability review;
the connector installs through normal native lifecycle approval. The job checks
saved revision and statistics under a fresh Alice session. Worker runtime must
remain identical. The helper records each phase before acting. Its state is in
`private/reference/worker/integration.json`. Worker provisioning phase is in
`private/reference/worker/state.json`; never replay an uncertain publication.

The earlier core23 rehearsal had five site installations/eight workspace activations,
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

That historical kit source snapshot is `5456abf4`. The core26 qualification has
its own [closure map](r1-release-checklist.md). Later audit receipts live in the
repository evidence index outside the source snapshot they verify.
