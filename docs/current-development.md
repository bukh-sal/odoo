# Current candidate development

Use this source-checkout path for new local development. The sealed-kit
[historical developer workflow](developer-guide.md#historical-sealed-kit-workflow)
keeps its own exact source and support boundary; it does not gain current code.
The [candidate support record](candidate-support.md) and [current status](implementation-status.md)
identify actual qualification. The public default-core build/plan/prepare/initialize/
publish path and fresh sign-in were [verified on an empty disposable site](evidence/G7/20261113-pp04-bootstrap-native-01/qualification.json).
The new independent app author/install/update/use walkthrough is still pending.

Native Python and same-origin frontend applications are trusted. This is an
owned fork, not a third-party addon compatibility or hostile-code sandbox.
Retain notices/licenses and keep independently owned applications in their own
repositories. Nothing here authorizes production, publication or deleting data.

## Prepare the checkout and build

From the project root, use the isolated [operator toolchain](operator-toolchain.md).
Do not replace a working environment or change global Python/PATH. Select the
explicit interpreter, then build the default eight-addon clean core into a new
evidence directory:

```powershell
$candidatePython = (Resolve-Path '.local/toolchain/operator-python16/Scripts/python.exe').Path
& $candidatePython -I tools/build_candidate.py --gate G7 --output docs/evidence/G7/MY-FRESH-CORE-BUILD
```

Docker/BuildKit and the locked Python/Node/OS/wheel prerequisites must be available;
see [clean builds](clean-candidate-build.md). A successful build is not a deployment
or application approval. Keep its exact image, build record and source inputs.
The bootstrap rejects changed curated hashes, application-containing policies,
mutable image references and failed/incomplete records. It also checks the actual
image inventory/core identity before creating persistent Docker assets.

## Bootstrap a disposable development site

Choose an absent project-owned directory, a free unprivileged loopback port and
two nonoverlapping private subnets. The following are examples; inspect your
host's existing resources before selecting them. **Plan is the default and
performs file validation only:** no directory, Docker or site creation.

```powershell
$candidateWork = Join-Path (Get-Location) '.local/development/MY-FRESH-SITE'
$candidateRecord = 'docs/evidence/G7/MY-FRESH-CORE-BUILD/candidate-build.json'
& $candidatePython -I tools/initialize_candidate.py --workdir $candidateWork `
  --build-record $candidateRecord --port 18601 `
  --runtime-subnet 10.205.61.16/28 --edge-subnet 10.205.61.32/28
```

Review those inputs, then run each separate phase once:

```powershell
& $candidatePython -I tools/initialize_candidate.py prepare --workdir $candidateWork `
  --build-record $candidateRecord --port 18601 `
  --runtime-subnet 10.205.61.16/28 --edge-subnet 10.205.61.32/28 `
  --disposable-development-site
& $candidatePython -I tools/initialize_candidate.py initialize --workdir $candidateWork --disposable-development-site
& $candidatePython -I tools/initialize_candidate.py publish --workdir $candidateWork --disposable-development-site
& $candidatePython -I tools/initialize_candidate.py status --workdir $candidateWork
```

Preparation generates and records exact names before any resource creation,
checks authoritative Docker absence/global subnet nonoverlap/port availability,
and creates two owned networks and six owned volumes. The seed provides explicit
development users, two workspaces and asymmetric roles. It is not production
onboarding. Initialization proves exactly eight installed core addons and zero
application installations/features/grants/bindings. Publication uses the normal
guarded worker, assets and release profile, then opens only the chosen loopback
port. No reference shell or application is installed or approved.

The private directory contains `site/state.json`, `site/fixtures.json`,
`site/account-passwords.json`, `site/operator/{trust.json,target.json,control/}`
and `catalog/`. Read the protected fixture/password files locally to sign in;
never paste credentials into logs, source or chat. Status prints the actual URL,
site phase and resource identities; after later lifecycle operations the current
`target.json` selects the real database/worker, not an old bootstrap name.

Operator policy requires interactive independent application approval by default.
Only an explicitly selected disposable qualification may pass
`--allow-noninteractive-operations` **during prepare**. That opt-in configures OS
policy, approves no app, and does not replace exact-hash review/required effect
acknowledgements. Existing sealed reference-kit behavior is unchanged.

## Author, admit and operate an application

The [independent application workflow](independent-app-workflow.md) walks through
current public packaging, local composition, nomination, separate approval and
real UI/diagnosis checks. Detailed installed acceptance remains recorded in the
phase evidence; the guide does not make unqualified combinations supported.

Follow [application authoring](application-authoring.md) for independent source,
ordinary recipes, native model/view/service/schema ownership and deterministic
archives; [native application surface](native-application-surface.md) distinguishes
demonstrated capabilities and limits. A clean core cannot install absent addon
bytes: build an explicit app-enabled composition, independently review/admit its
exact archive and use [normal staging/planning/approval/apply](application-operations.md).
Application code never receives the OS approval store or issuer secrets.

The method's registered model guard runs before cached mutation outcomes return;
handler-only provider checks do not protect saved derived DTOs. If returned data
requires current provider access, protect it in that model guard (and native
reads) while keeping unrelated independent operations available. PP03 found and
qualified this distinction in Taskfiles; generic idempotency does not rerun effects.

## Inspect an interruption

Exclusive phase/command intents and completion hashes are outside the database.
After a timeout, disconnect, refusal or missing completion, inspect `status`,
the durable target and private `site/logs` **before any next mutation**. A marker
does not prove an operation is still running. Do not delete an intent, reset a
volume, repeat a partial phase or guess that apply/restore did not happen.

This command deliberately provides no reset/prune/prefix-deletion operation.
Retain the exact site/images/checkpoints or prepare a separately reviewed exact
ownership cleanup. Unresolved-failure recovery remains separately reviewed with
fresh database and separate resume. Completed-checkpoint restore is still PP04
implementation work, not an existing promise or a reason to bypass a guard.
