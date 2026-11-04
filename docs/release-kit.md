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
records the actual source overlays and narrow pre-data DNS continuation. External
worker and complete twelve-case operational handoff still require qualification.
No full G7 claim follows from these commands.

The worker is a separate operator action, after that backend walkthrough:

```powershell
.local/release-kit-rehearsal/operator/Scripts/python.exe -I .local/release-kit-rehearsal/source/release/initialize_worker.py --kit .local/releases/r1-0.1.23 --workdir .local/release-kit-rehearsal
```

This new once-only helper is awaiting its first qualification. It starts the
locked reference Compose worker on the existing internal network, provisions
new scoped keys and two dedicated volumes, then independently reviews/publishes
the exact authority hash. It does not install metadata or select a connector;
those and an actual queued job remain required. Its phase is in
`private/reference/worker/state.json`; never replay an uncertain publication.
