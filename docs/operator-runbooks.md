# R1 local operator runbooks

These procedures cover spec24.4's twelve cases for the trusted-native,
single-host reference profile. G7 remains open; use the
[status](implementation-status.md) and the selected target's independent journal
for current identities. Historical evidence proves its recorded environment;
it is never an instruction to rerun an old fixture driver. The public
[release kit](release-kit.md) contains distribution inputs. A site recovery kit
also needs privately retained data, control, configuration and current authority.

Prepare the CLI context from the chosen operator workspace, without printing
its private files. For the documented rehearsal:

```powershell
$mpWork = Resolve-Path .local/release-kit-rehearsal
$mpSetup = Get-Content "$mpWork/operator-setup.json" -Raw | ConvertFrom-Json
$mpPython = $mpSetup.python
$mpSource = $mpSetup.source
$mpReference = Join-Path $mpSetup.private reference
$mpTrust = Join-Path $mpReference operator/trust.json
$mpControl = Join-Path $mpReference operator/control
$mpTarget = Join-Path $mpReference operator/target.json
$mpCatalog = Join-Path $mpSetup.private catalog
$mpWorker = Join-Path $mpReference operator/worker-target.json
$mpCli = @('-I', "$mpSource/tools/modular.py", '--config', "$mpTrust")
$mpTargetArgs = @('--deployment-config', "$mpTarget", '--catalog', "$mpCatalog")
```

Select `$mpOperation`, `$mpPlanHash`, bundle/decision paths and review hashes
from the actual new proposal/journal. No example operation ID authorizes work.
Private command outputs can contain personal data; store them under the SDK's
owner-verified directory and redact/scan before sharing. Keep the target/control
outside application mounts. Commands below omit `--noninteractive`: the
rehearsal's explicit policy permits it, but it is not a general default.

## 1. Fresh deployment

Verify the kit inventory, create a new isolated operator workspace, then follow
the once-only prepare/initialize/install/check/worker/integration sequence in
[release-kit.md](release-kit.md). Select an unused loopback port and accept only
new named disposable storage. Do not copy old SQLite catalogs, application
data, approvals or issuer keys into this public-input installation.

Confirm the actual immutable images/inventory, independent completed journals,
native Notes list/form descriptors, scoped asymmetric sessions, minimal Canvas
and the original-actor worker job. A phase failure requires reconciliation of
that phase's marker/process/effects; never reset the workspace or repeat core
initialization. This does not deploy a production service.

## 2. Plugin install and permission approval

Inspect the archive's exact digest, manifest, source/trust, native runtime and
permission declarations. `plugin validate <archive> --digest <sha256:...>` checks
against the selected independent trust file; it does not curate or approve it.
Import reviewed bytes with `catalog --store $mpCatalog add <archive> --digest
<sha256:...>`. A digest outside the separately maintained allowlist stays refused.

Create a scoped proposal in the manager, then use `operations --store $mpControl
import-request $mpOperation` with `@mpTargetArgs`, or register a locally prepared
bundle. The exact ordinary register/review/approve/apply path is:

```powershell
& $mpPython @mpCli operations --store $mpControl register --bundle $mpBundle @mpTargetArgs
& $mpPython @mpCli operations --store $mpControl approve $mpOperation --plan-hash $mpPlanHash --ack-trust --ack-permissions @mpTargetArgs
& $mpPython @mpCli plugin apply $mpOperation --store $mpControl @mpTargetArgs
& $mpPython @mpCli operations --store $mpControl show $mpOperation
```

Use either import or local registration for a new operation. Review dependency
closure, all sharing sites/workspaces, image pin, grant/binding changes and any
native maintenance/destruction. Add destructive acknowledgment only after
reviewing that exact destructive plan. App requests/cached approval flags and
curated trust never replace the independent approval. Verify current feature,
native schema/view and permission outcomes after completion.

## 3. Schema upgrade

Build/inspect a separately selected immutable candidate with exact dependency
and native migration inputs. Use `plugin stage-image --image-id <sha256:...>
--store $mpControl @mpTargetArgs`, then `plugin plan-staged --input <nomination>
--store $mpControl @mpTargetArgs`, or the manager's equivalent nomination.
Review adjacent/skipped transition coverage, preconditions, checkpoint policy
and the complete site-wide closure. Follow case2 with the resulting exact bundle.

Before native work, the executor fences dispatch, drains traffic and records its
coordinated checkpoint. Verify schema/data/inventory, new release epoch, native
views and old-client fencing after completion. An uncertain commit takes case5;
it is not a reason to rerun a migration or edit its version record.

## 4. Failed startup

Inspect the current target, independent operation journal, exact created child,
exit state and protected diagnostics. Distinguish a rejected startup inventory,
missing/invalid configuration and a native mutation that may have committed.
Do not fall back to a floating image, disable the startup guard, recreate volumes
or restart an unknown migration. Stop if a surviving child can still mutate.

If the journal/actual observations prove no mutation occurred, use the separately
reviewed `prepare-unchanged-resume`/`resume-unchanged` protocol, with the exact
decision and hash. Otherwise follow case5. Check image/inventory/current authority
and readiness before separately reopening traffic. See
[startup boundary](runtime-startup.md) and [operations](operations.md).

## 5. Failed migration

Keep traffic and dispatch fenced. Inspect `operations ... show`, stage records,
child state and checkpoint hashes. Preserve the failed source database and
filestore; an uncertain native commit is `recovery_required`, never a replayable
ordinary failure. Never repair the journal into a completed state.

```powershell
& $mpPython @mpCli plugin recover prepare-restore $mpOperation --store $mpControl @mpTargetArgs
& $mpPython @mpCli plugin recover restore $mpOperation --decision $mpDecision --decision-hash $mpDecisionHash --store $mpControl @mpTargetArgs
& $mpPython @mpCli plugin recover prepare-resume $mpOperation --store $mpControl @mpTargetArgs
& $mpPython @mpCli plugin recover resume $mpOperation --decision $mpResumeDecision --decision-hash $mpResumeHash --store $mpControl @mpTargetArgs
```

Save each returned private review; inspect target/checkpoint/current authority
and its exact hash before the corresponding execution. Restore creates a fresh
named database. Before resume, verify records/schema/files, newer release and
dispatch epochs, session rotation, revoked technical credentials, old-client
and failed-plan refusals. Restore/resume are separate reviews. Expired, altered,
revoked or mismatched reviews must be newly prepared, never extended by editing.
[Current combined recovery evidence](evidence/G7/20261104-native-uninstall-recovery-01/qualification.json)
and [recovery profile](recovery-rehearsal.md) define its bounded guarantees.

## 6. Worker outage

Inspect the separately operated worker's exact container/image, internal address,
health, public-only mount and current endpoint/key generations. Pending/retry
jobs remain tied to their saved original actor/revision; unavailable optional
analysis must not disable Notes CRUD. Inspect a job's actual outcome before any
another dispatch, especially if an outbound result may already exist.

Use the fixed operator-owned worker Compose configuration to repair that runtime.
A new address/key/configuration needs a newly prepared/reviewed publication;
health JSON cannot authorize it. Native/plugin lifecycle does not start or
replace external workers. Run one guarded job using `worker --store $mpControl
--deployment-config $mpTarget --worker-config $mpWorker run-job-once` only after
current authority/runtime is verified. See [worker authority](worker-authority.md).

## 7. Expired or revoked credentials

Confirm the real actor, scope, current membership/grant and independent issuer
publication. Expired/revoked credentials remain denied; do not lengthen a saved
token, restore old authority or use an administrator as the saved actor. Review
and provision new immutable key references when rotation is required. Prepare
and independently exact-hash publish the new scoped endpoint/key generation.

Reauthenticate human sessions after recovery, use fresh current client pins,
and prove old sessions/tokens/plans fail while the new authorized path works.
Observe original-actor finalization after any revocation during work; a result
does not itself grant permission to apply it.

## 8. Backup and restoration

For native maintenance, retain the executor's coordinated
`operator/control/checkpoints/<operation>` database dump, selected-site filestore
archive and exact manifest plus journal/stage records. Verify archive hashes and
readability, and retain the previous image/source/artifact/dependency inventory.
An uncoordinated live `pg_dump` alone is not a complete site backup. This runbook
uses the qualified maintenance checkpoint path; no standalone scheduled-backup
command is claimed.

Retain private app/db configuration and current independent control/issuer
authority separately, under an explicit retention policy. The public kit contains
none of these. Application DB rollback must not resurrect old memberships,
credentials, approvals or issuer generations. Rehearse restoration to a fresh
database through case5 and verify data/files/native views/authentication before
resuming. The retained failed source and checkpoint are not cleanup candidates
merely because recovery succeeds.

## 9. Compromised native plugin

Treat all application data/configuration reachable by trusted native Python as
potentially exposed. Close ingress and stop new job dispatch; preserve the
independent journal, runtime/source identities and private diagnostic evidence.
Use independent operator authority to revoke pending approvals and affected
scoped endpoint/credential access. Do not execute an untrusted plugin's uninstall
hook as the first containment action.

Select a reviewed clean image and separately reviewed recovery/removal plan.
Rotate exposed database/session/technical secrets and assess data integrity and
exfiltration separately. Restore cannot retract disclosed data or undo unknown
external effects. Same-origin frontend/native grants are not a sandbox. Reopen
only after clean inventory, authority and scoped behavior are verified.

## 10. Artifact/catalog trust failure

Stop the affected plan before execution. Retain the exact offending archive and
diagnostic privately; inspect digest/signature mode, canonical inventory,
entry/size/ratio/path limits and current catalog trust generation. Do not add
unsigned-development bypasses or let artifact declarations change trust policy.
Quarantine a rejected digest through `catalog --store $mpCatalog quarantine
<sha256:...>` under independent operator control.

Obtain separately reviewed known-good bytes/trust and prepare a new current plan.
A changed allowlist or artifact invalidates the old review. If native bytes have
already executed, use case9 and the actual recovery journal rather than merely
removing a catalog row. See [packaging](packaging.md).

## 11. Upstream patch or security update

Reconcile dated advisories against actual OS/Python/native/vendored inputs,
affected source and existing support/backport evidence. Record disposition,
residual risk, source/license notices and review triggers. Current local-reference
acceptance is not a zero-vulnerability or production-safety assertion. The dated
residual decisions require review by their recorded deadline or a relevant change.

Pin candidate dependencies/source/images, retain upstream notices and record
substrate changes in [upstream patches](upstream-patches.md). Rebuild/verify the
declared inventory, affected behavior, licenses and secret/network boundaries.
Use normal stage/approval/upgrade/recovery flow; revalidate changed G2 contracts
before rollout. Do not edit the qualified image in place or equate a version
bump with a verified fix. See [provenance](provenance.md).

## 12. Data export and destructive removal

Use authorized scoped Notes services/native views for record access. A complete
operator recovery export is case8's private DB/filestore/configuration/authority
set; the public distribution kit is not a personal-data export. Verify an export's
readability, scope and retention before any destructive proposal. No broad
unauthenticated export or new attachment feature is implied.

Preview dependencies and every workspace sharing the native installation. Native
uninstall/removal requires independent exact-hash destructive approval and its
coordinated checkpoint. Feature suspension retains data and executable code;
it is a different operation from native uninstall, source removal or data purge.
Verify the intended schema/data/source effects and foreign-scope preservation.
Real user data and backup retirement require explicit retention authorization;
this project only authorizes clearly named disposable fixtures. Never use a
global Docker prune or delete unknown databases/volumes. See
[retention](artifact-retention.md) and current recovery evidence.

These runbooks still need their final current-kit operator walkthrough and G7
cross-check. Their existence alone does not pass OPS-03 or award release progress.
