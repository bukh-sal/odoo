# R1 developer entry point

R1 qualification is still in progress. Read [current status](implementation-status.md)
and the [release checklist](r1-release-checklist.md) before choosing a kit. The
existing `r1-0.1.23` draft predates the current shell and operator tools; this guide
is source for the final kit, not a claim that the draft contains these additions.
Keep the upstream README and license notices intact.

## Start a new disposable installation

Use the exact kit selected by the operator and the commands in
[release-kit.md](release-kit.md). Verify its inventory before extracting or
executing it. Its setup creates an isolated Python environment without changing
global Python. The new work directory must not exist beforehand. Run each phase
once and inspect recorded state after an interruption; do not initialize an
existing database or copy the author's private state.

After setup, use its recorded paths in PowerShell (replace the first path with
your new work directory):

```powershell
$mpDevWork = 'C:\absolute\path\to\your-new-workdir'
$mpDevSetup = Get-Content -Raw -LiteralPath (Join-Path $mpDevWork 'operator-setup.json') | ConvertFrom-Json
$mpDevPython = $mpDevSetup.python
$mpDevSource = $mpDevSetup.source
```

The documented sequence is `initialize_reference.py prepare`, `initialize`,
`install`, then `check_reference.py`. The prepare command requires the explicit
`--reference-fixture` flag for its disposable unattended approval profile. These
commands create distinct accounts, two workspaces, two Notes and one minimal
Canvas. Read the protected account-password file named in the setup guide;
never put passwords into source, example commands or logs. The protected
reference state records the URL. Standard Notes screens use native Odoo lists
and forms; Canvas is the optional custom-page example.

The reference worker is a separate operator action, using
`release/initialize_worker.py`, as documented in the kit guide. Registering its
metadata does not start the process. Its own image/configuration/issuer and
endpoint approval remain separate from native plugin installation.

## Read and extend a native example

Work in a separate disposable source checkout/copy, not the installed source or
an immutable catalog blob. For the first exercise retain the repository example
IDs; a third-party plugin needs its own reverse-DNS ID, addon mapping, schemas,
field/contribution ownership and permission inventory. The reference assembler
deliberately accepts only the five repository examples.

Follow these paths from that source root:

| Path | Responsibility |
| --- | --- |
| `plugins/notes/plugin.toml` | Package metadata, public services, permissions and native page declarations |
| `platform_addons/mp_example_notes/models.py` | Workspace ownership, role checks, public UUID DTOs and revision CAS |
| `platform_addons/mp_example_notes/views/notes.xml` | Native list/form definitions; retain these for ordinary CRUD |
| `plugins/notes_labels/plugin.toml` | Declared dependency/binding, extension field ownership and UI contribution |
| `platform_addons/mp_example_notes_labels/models.py` | Native `_inherit` extension, availability guard and cooperative base write |
| `platform_addons/mp_example_notes_labels/static/src/labels.js` | Contribution handler using the host API |

For a bounded packaging exercise, change the Labels contribution's visible label
in `plugins/notes_labels/plugin.toml`. Increase its package version from `0.2.4`
to `0.2.5` and native manifest version from `19.0.0.2.4` to `19.0.0.2.5` in the
isolated copy. Change no grants, bindings or field semantics. Never publish
different bytes for an existing `(plugin_id, version)`.

Create an output directory explicitly, then package it:

```powershell
$mpDevCheckout = 'C:\absolute\path\to\your-disposable-source-copy'
$mpDevOutput = 'C:\absolute\path\to\your-existing-artifact-directory'
& $mpDevPython -I (Join-Path $mpDevSource 'tools/package_reference.py') --source $mpDevCheckout --example notes_labels --output (Join-Path $mpDevOutput 'notes-labels-0.2.5.mplug')
```

The assembler reads native Python as data, maps package/native versions, includes
schemas/notices and produces deterministic inventory/provenance. It refuses an
existing output. Its digest is an identity, not an installation or trust grant.
Independently review the exact archive and select its digest in an operator-owned
curated configuration before `plugin validate` / catalog admission; see
[packaging.md](packaging.md). Review native code as fully trusted code.

Adding or changing stored fields requires explicit data ownership, guarded native
access, public schema/version decisions and applicable migration files/digests.
Suspension does not unload native classes. Keep the original actor, current
workspace, role checks, named bindings, idempotency and expected revision checks;
do not use `sudo` to make the example work. If changing the Labels payload,
coordinate its schema, contribution handler and consumers rather than bypassing
validation. Existing Notes/Labels demonstrate an actual shared-table extension;
the label exercise only qualifies packaging and version discipline.

## Host a custom page

`packages/host_sdk/src/index.ts` defines `PluginPageModule`; the plain TypeScript
example in `packages/host_sdk/tests/plain_page.ts` has no Owl dependency. The
installed reference implementation is
`platform_addons/mp_example_canvas/static/src/page.js`, with its native adapter
and manifest asset declarations. `plugins/canvas/plugin.toml` declares the page,
navigation and required `documents` binding.

For the second isolated exercise, change the Canvas subtitle in `page.js`, bump
its package `0.1.4` to `0.1.5` and native `19.0.0.1.4` to `19.0.0.1.5`, then run:

```powershell
& $mpDevPython -I (Join-Path $mpDevSource 'tools/package_reference.py') --source $mpDevCheckout --example canvas --output (Join-Path $mpDevOutput 'canvas-0.1.5.mplug')
```

This is an exercise in a separate copy, not Canvas product development. Keep
`mount`, `updateRoute`, disposal/AbortSignal and dirty recovery behavior. Use the
provided host context/services/navigation/dialog APIs; do not invent a second
action stack or depend on private session/company/ORM state. Native Odoo already
supplies standard view, dialog, notification and command infrastructure. Custom
pages remain optional; same-origin pages and native Python are trusted, not
sandboxed by grant metadata.

## Install, validate permissions and recover

Packaging alone never deploys code. New native executable bytes require a
candidate containing the exact admitted artifacts, followed by independent
`plugin stage-image`, `plan-staged`, `operations register`, full exact-hash review,
approval and `plugin apply`. Use the operator-selected policy/catalog/target and
the CLI's `--help`; see [operations.md](operations.md) and
[operator-runbooks.md](operator-runbooks.md). Do not call `-u`, edit a running
container, replace its release lock or reuse a completed operation. If dependency
inputs are unchanged, ADR0052 describes the exact-image code-maintenance path;
changing dependencies requires their own qualification.

On a fresh disposable fixture, verify the administrator/editor can use the
enabled feature, a viewer cannot mutate it, the other workspace cannot read its
record even by a known URL/public ID, and suspension blocks the feature's API
and contribution. Browser visibility is not authorization. Check ordinary native
list/form screens as well as the custom page; keep workspace/session identity
separate in two tabs. See the ID/TEN/API/UI acceptance ledger and existing tests.

Use the failed-startup/migration and backup/restore runbooks for a deliberately
failed disposable fixture upgrade. Observe the independent operation journal and
actual maintenance child first. Keep the failed database and checkpoint; recover
into a new named database through a separately reviewed restore, reconcile
effects and separately resume traffic. A heartbeat is observation, not proof
that work advanced or permission to retry. Unknown external effects must not be
automatically replayed. [Recovery evidence](recovery-rehearsal.md) records the
qualified profiles and their limits.

Current source-only packaging proof is linked from the status ledger. Final
§28 completion still requires the qualified final kit and actual fresh-developer
install/extension/custom-UI/permission/recovery/worker walkthrough; these written
commands and package validation alone cannot satisfy it.
