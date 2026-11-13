# Operate a local application release

For a new current checkout, use [current candidate development](current-development.md)
and the isolated [operator toolchain](operator-toolchain.md). Historical adoption
kits keep the [application development](application-development.md) path for their
own recorded sources. The exact OS-owned target,
catalog and journal govern operations. An app's proposal or a build receipt
never grants execution authority. The commands below are separate reviewable
steps, not an automatic approval wrapper. All examples are for named local
synthetic development deployments.

## Inspect and install

Choose an existing deployment's private operator directory. Obtain the actual
site ID, image and selected package digest from its target/verified runtime;
do not substitute a remembered bootstrap name after restore or upgrade.

```powershell
$adControl = '.local/MY-SITE/operator'
$adCli = Join-Path $adSource 'tools/modular.py'
$adTrust = Join-Path $adControl 'trust.json'
$adTarget = Join-Path $adControl 'target.json'
$adCatalog = Join-Path $adControl 'catalog'
$adStore = Join-Path $adControl 'control'
& $adPython -I $adCli --config $adTrust catalog --store $adCatalog list
& $adPython -I $adCli --config $adTrust jobs --store $adStore --deployment-config $adTarget status
```

Independently review source and the exact digest before adding it to the curated
trust configuration/catalog. A trust generation change is intentional and must
match current bytes. Existing lifecycle validation refuses stale configuration.
For a package already in the selected image, nominate its explicit site-native
installation (dependency closure appears in the resulting bundle):

```powershell
& $adPython -I $adCli --config $adTrust plugin plan-current-install `
  --deployment-config $adTarget --store $adCatalog --operator-store $adStore `
  --site SITE-ID --site-native --plugin dev.aurora.projects_tasks `
  --version 0.1.1 --digest REVIEWED-EXACT-SHA256
```

Save returned JSON as UTF-8 **without a BOM** in the private directory. Review
the whole operation/lock: sites, packages, dependencies, versions, image, required
maintenance/checkpoint, permissions and destructive effects. Register the exact
saved bundle, then inspect its journal before approving:

```powershell
& $adPython -I $adCli --config $adTrust operations --store $adStore register `
  --bundle "$adControl/install.json" --deployment-config $adTarget --catalog $adCatalog
& $adPython -I $adCli --config $adTrust operations --store $adStore show OPERATION-ID
& $adPython -I $adCli --config $adTrust operations --store $adStore approve OPERATION-ID `
  --plan-hash REVIEWED-EXACT-PLAN-HASH --deployment-config $adTarget --catalog $adCatalog
& $adPython -I $adCli --config $adTrust plugin apply OPERATION-ID `
  --store $adStore --deployment-config $adTarget --catalog $adCatalog
```

Interactive approval prints the current independent review and requires its exact
hash. Acknowledgment flags are required only for effects actually present in the
review. Noninteractive qualification uses explicit `--noninteractive` plus an
OS policy that allows disposable testing; it is not implied by this guide.
`plugin apply` routes current-image versus staged-image executors from the
immutable bundle. Do not select those low-level SDK executors by guesswork.

## Stage and upgrade applications

Admit the reviewed successor archives separately, then stage the exact composed
image with `plugin stage-image --store ... --deployment-config ... --catalog ...
--image-id sha256:...`. Save/review its descriptor. Use `plugin plan-staged` with
the same three arguments and `--input PRIVATE-NOMINATION.json`:

```json
{
  "operation_type": "upgrade",
  "targets": [
    {"installation_id":"EXISTING-ID","site_id":"SITE-ID","workspace_id":null,"plugin_id":"dev.aurora.projects","action":"upgrade"},
    {"installation_id":"EXISTING-EXTENSION-ID","site_id":"SITE-ID","workspace_id":null,"plugin_id":"dev.aurora.projects_tasks","action":"upgrade"}
  ]
}
```

Include only actual selected changes. Review/register/approve/apply the resulting
exact bundle as above. Staging alone changes no live installation and approves
nothing. Unknown transitions, conflicting dependencies, source/environment drift
or unavailable scoped authority require reconciliation, not a forced apply.

## Failure, restore and separate resume

Inspect `operations ... show OPERATION-ID` first. The journal distinguishes
unconsumed approval, mutation started, recovery required, restored closed and
completed. Inspect private logs/checkpoint hashes and current target. Never replay
an uncertain apply, reset a volume or delete its intent marker to start over.

Use `plugin recover` with the same store/target/catalog arguments:

1. `prepare-restore OPERATION-ID` returns an independently reconstructed decision
   and its hash. Review original image/checkpoint, fresh database, current
   authority, files, jobs and the closed-traffic requirement.
2. Save the **decision object** as UTF-8 JSON. `restore OPERATION-ID --decision
   PRIVATE-DECISION.json --decision-hash EXACT-HASH` executes only that decision.
3. Verify restored rows/files/auth/job classification while traffic remains closed.
4. `prepare-resume OPERATION-ID` produces a distinct current resume decision/hash.
   Review/save it; `resume OPERATION-ID --decision PRIVATE-RESUME.json
   --decision-hash EXACT-HASH` is a separate action.
5. Verify useful native work and actual effects, then prepare a fresh forward
   operation if needed. The consumed/revoked failed operation is not reusable.

Use the updated host operator for native-job recovery (ADR0079). Valid original
jobs are reconciled against the checkpoint/current publication while dispatch
stays closed; revoked actors stay held. No app-supplied actor override or forced
retry. Business-role relationships restore to checkpoint; native authentication
and platform revocations have their explicit current-authority reconciliation.

## Workers and pilot stop/start

`jobs ... status` reports actual dispatch and managed lane state; `metrics` reports
queues. Web startup alone does not run reminder workers. Review a bounded fleet:

```powershell
& $adPython -I $adCli --config $adTrust jobs --store $adStore --deployment-config $adTarget profile-review `
  --urgent-lanes 1 --bulk-lanes 1 --producer-lanes 0 --shutdown-seconds 5
& $adPython -I $adCli --config $adTrust jobs --store $adStore --deployment-config $adTarget profile-apply REVIEWED-APPROVAL-ID
```

For a planned stop, run `jobs ... drain`, verify no lanes, then inspect the exact
current worker ID and project from target/intent. Stop its edge, current web worker
and database, retaining volumes. Drain pauses/removes managed lanes; it does not
itself pause database dispatch. Lifecycle maintenance closes dispatch separately.
On an unchanged restart, start the same database and wait for `pg_isready`, then
the exact current web worker/readiness, then edge. Review/apply a fresh fleet
approval for the selected pins. Never reuse consumed approvals or change images
inside an ordinary restart. [Pilot instructions](application-pilot.md) identify
the intentionally retained targets and private credential locations.

Cleanup is a separate final action: verify container images/labels/mounts and
volume/network ownership against the selected site's recorded inventory before
removal. Keep private evidence/checkpoints and sealed releases. Retire only
obsolete named disposable targets and their unused image aliases; no blanket
Docker prune or prefix-based deletion of unrelated historical/user assets.
