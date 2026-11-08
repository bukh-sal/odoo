# ADR0077. Review native Tasks adoption as one closed foundation transition

Accepted8 November2026 for AT-04 after AT-03 actual-image checks passed. Preserve
sealed47/46 and the existing46→47 recipe. This adds a separate owned47→49 recipe;
it does not support external Odoo addons or arbitrary legacy adoption.

## Why a separate transition is required

The supported old Tasks0.1.0 app on sealed47 has native records and no package
registration. The qualified application candidate48/Tasks0.2.2 proves current
installation and jobs, not adoption of that old data. Ordinary install correctly
refuses an already installed unregistered native addon. Ordinary core maintenance
correctly requires unchanged package archives and cannot add its first package.
Do not insert unreviewed metadata, fabricate a prior artifact, reuse46→47, or
relax those ordinary paths.

Select `owned-native-tasks-adoption-47-49-v1` explicitly in the private stage
declaration. New operator/recipe support belongs to separately identified core49;
the useful application archive remains the qualified0.2.2 bytes. Preserve the
same final foundation image for independently configured Tasks and Maintenance
deployments, even when Maintenance has no Tasks installation.

## Exact authority and plan

- Bind sealed47 image/inventory, exact target49 image/inventory/policy, complete
  source changes, unchanged Python environment, recipe/child source hashes and
  the one admitted Tasks0.2.2 artifact. All five existing reference archives stay
  byte-identical. Available native addon names stay unchanged; only core and
  Tasks native manifests have the declared version/dependency/data changes.
- Only the distribution's explicit application recipe is added. No unrelated
  policy, endpoint, binding, permission, trust, source-root or dependency change.
  Reject unknown recipes, modules, commands, SQL and unstated native/data effects.
- Observe the real installed modules and absence of Tasks package metadata. If
  native Tasks0.1.0 is installed, nominate its canonical site-native metadata
  installation in the plan, explicitly displayed as **adoption and native
  update**. It has NULL workspace and creates no workspace/grant/binding. Native
  execution updates the already installed module; metadata installation registers
  the first actual package after that update.
- If Tasks is absent, it remains absent. The same image may make its archive
  available without installing it or creating metadata. This reviewed exception
  only admits this exact new archive; it does not make other transitive artifact
  changes target-free. Every existing native installation scope remains covered.
- Use the existing core operation, site scope, immutable lock/hash, independent
  stage reconstruction, OS approval, destructive/checkpoint acknowledgement,
  drain, restart, readiness and publication. The closed declaration is an explicit
  trusted planner parameter, not an application-supplied request flag. Its exact
  contents remain in the hashed operation lock and review display.

## Data and execution

Before approval and again after drain, bind installed module versions and fixed
application table witnesses. Privately capture the old task/list/stage/member
rows under the original schema; checkpoint the complete DB and filestore before
any native update. Fixed reviewed identifiers and columns only, no caller SQL.
Preserve existing task/list/stage/member IDs, all original column values, ownership,
assignment, dates and membership. Existing tasks acquire reminders disabled and
revision1. The declared post migration may add only the previously missing open/
done choices, one per missing list/meaning; preserve every old stage and task value.
The two new occurrence/inbox tables must be empty before traffic is admitted.

For Maintenance, preserve its fixed business-table witnesses and selected native
module set. The Tasks addon/package remains available and uninstalled when absent
before the update. No communication/core extraction or source retirement occurs.
After native update, verify these effects before publishing metadata or traffic.
The normal validated native-site metadata child creates only the declared package
installation. Readiness must independently observe exactly that planned state.

Pending workspace and native jobs retain original actors, resources, payloads,
timing and deduplication identities under the existing generation/reconciliation
fences. The supported source47 has no native reminder jobs: those are first
introduced by this application update. Prove pending native jobs across a later
real release publication as well; a rollback-only classifier is insufficient.

## Recovery and required evidence

Fail after a real commit/publication boundary while ingress stays closed. Keep
the failed database/image and independent journal. Restore the original checkpoint
into a fresh named database with original47 code, native0.1.0 app and its unregistered
package state. Reapply current independent revocations/fences and preserve task/
membership/files/data witnesses. A separately reviewed resume is mandatory; no
automatic redispatch or uncertain effect replay. Recognize only this recipe's
specific new schema/metadata effects in restore checks.

Keep a separately configured Maintenance peer useful during the outage. Qualify
native workflows and real jobs there, then verify the recovered Tasks app. Final
target qualification includes clean install, populated update, final native browser,
job carry-forward, affected regressions, reproduction/privacy and exact retirement.
Schema/plan tests, documentation and diagnostic overlays add no runtime credit.

Freeze the compatible private contract/fixtures and prove independent planner
reconstruction before mutation. Existing46→47 goldens and generic negative guards
must keep passing. This decision is a required implementation plan, not a claim
that the transition, recovery or final core49 image already exists.
