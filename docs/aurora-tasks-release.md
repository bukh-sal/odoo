# Aurora Tasks on the owned foundation

Shared lists, stages, assignment, due dates, completion, durable reminders and
a private recipient inbox use native WebClient actions and list/form views.
This is our independently owned fork, with no external Odoo compatibility goal.
Canvas remains a minimal optional custom-page example.

The [checklist](implementation-status.md) is authoritative. The local kit is
qualified only when `qualification/foundation-release.json` declares the exact
AT profile passed and `scripts/verify.py` verifies its checksums. Progress files
inside its source archive are dated development records.

## Artifacts

- Foundation`0.1.49`, contract revision25.
- Image`sha256:cac49d72605fe62a13b262c4775a0c55da6052f1743fb2b6d6b667a8a877de7f`.
- Inventory`sha256:d490c3d7701a4b0aa48edb6508a322bc3a7faf005ca976cf9dae6ce6b543a3a6`.
- `dev.aurora.tasks` version`0.2.2`, addon`mp_aurora_tasks` version`19.0.0.2.2`.
- Archive`sha256:71c97db1113cba7ba664171962208e429ecff66feb2ef8433e966a1ef20aa52c`.
- Sealed local kit`.local/releases/foundation-r1-core49-tasks` (57components).
- Manifest`396054faa70542a167ac5cd5e309579270e030cfbe4bb22c155b08c7bd215404`.
- [Qualification](evidence/post-r1/aurora-tasks/qualification-decision.json) and
  [final verification](evidence/post-r1/aurora-tasks/final-delivery.json).

Sealed core47/core46 artifacts stay unchanged. Convenience tags confer no
authority; operator actions bind immutable image/inventory/artifact identities.

## Author and install an application

Follow [application authoring](application-authoring.md), with explicit owned
sources, package/native dependencies and notices. Use new versions for changed
bytes. The general builder accepts non-example identities; structural validation
and reproducibility grant neither curated trust nor executor approval.

Standard records use native models, ACLs/rules, views/actions/menus. Choose real
native or workspace ownership. A site-native app declares activation`["site"]`
and`supports_feature_suspension=false`. Use `plugin plan-current-install
--site-native` with the actual site/plugin/version/digest and normal protected
operator/config/catalog arguments, then independently register, review, approve
and apply. This creates no workspace, membership, feature or grant. Ordinary
install refuses already installed unregistered native addons.

The [behavior contract](aurora-tasks-contract.md),`applications/mp_aurora_tasks`
and`plugins/aurora_tasks/application.toml` are the concrete example. Workspace
jobs keep workspace/service authorization; native reminders keep their human
origin and native resource permissions. Neither trusted-code path is a sandbox.

## Upgrade the supported populated source

Only the exact sealed47 source/native states are admitted by
`owned-native-tasks-adoption-47-49-v1` ([ADR0077](architecture-decisions/0077-native-tasks-adoption-47-49.md)).
The old46→47 recipe stays separate. Do not relabel another source, manually
register metadata, or reuse a failed operation.

1. Use the selected kit's isolated interpreter and protected private operator
   directory, with the actual deployment/site identities.
2. Run `tools/review_foundation_transition.py --recipe
   owned-native-tasks-adoption-47-49-v1 --deployment-config <private-target>
   --image-id <exact49-image> --output <fresh-private-declaration>`.
   It observes current data and declares effects; it approves nothing.
3. Review source/image/recipe identities, installed native states, business-table
   witnesses and missing stages. Use `plugin stage-image --foundation-transition
   <declaration>` with the normal store/config/catalog arguments.
4. Prepare the staged `core_upgrade` nomination. Include every existing native
   plugin scope as`deploy` and, when old Tasks is installed, the canonical
   site-native adoption target returned by the recipe. Absent Tasks stays absent.
5. Register/review/independently approve the exact plan/hash, including destructive,
   trust and new site-scope declaration acknowledgments. The executor closes
   ingress/dispatch, drains and checkpoints before mutation. Changed witnesses
   require fresh review.
6. Apply once. Execution updates the existing native addon, preserves original
   task/list/stage/member rows and files, adds only missing open/done stages, then
   registers the first real package. Old tasks start with reminders disabled and
   revision1; no historical notices are inferred from due dates.

## Execute jobs and recover

Managed job lanes run beside each independently configured application database.
A bounded starting profile has1urgent and1bulk lane, separately reviewed through
`jobs profile-review`/`jobs profile-apply`. The web process alone supplies no
reminder capacity. Read-only pool advice is not automatic scaling approval.

Reminders are opt-in, up to30days ahead with a24hour validity window and a30second
attempt budget. The effect is an in-app database notice, not email/SMS/push.
Changes, completion, archive and revocation can invalidate delivery. Unique
effects/fencing prevent duplicate notices even when compute runs again. After
publication, original scheduled times/deadlines remain; overdue physical queue
eligibility may be rebased to reconciliation time. Revoked held work does not
execute automatically. Native technical-origin jobs, native recurrence and
external provider effects are outside this application's selected contract.

A possible commit/publication failure keeps traffic closed. Inspect the independent
journal; never replay uncertain apply. Review `plugin recover prepare-restore`
and restore to a fresh named database with checkpoint code. Preserve failed data
for diagnosis. Current revocations/fences are reconciled before startup. Separately
review`prepare-resume`/`resume` before opening traffic. A later forward attempt
uses a new declaration and operation. Actual qualification proved fresh47 recovery,
retained native ownership, post-checkpoint workspace revocation, stale-claim denial,
separate resume and useful Maintenance/16new jobs during the outage.

## Delivery boundary

Verify kit checksums and qualification before use; follow`setup_operator.py` for
an isolated environment. Source, reviewed archives, locked toolchain, exact images
and notices are included. Existing credentials, approvals, databases, filestores
and private checkpoints are excluded. Checksums are not publisher authentication.
This local development qualification authorizes no production deployment or
publication. Full Aurora import, standalone tasks, branding, extra app features,
brokers and automatic scaling remain excluded or conditional on later evidence.

Qualification targets are retired after proof; private logs/checkpoints/catalogs
remain under`.local/aurora-tasks`. New work uses fresh targets, never replayed
retired fixture commands or global Docker cleanup.
