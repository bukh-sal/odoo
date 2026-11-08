# Aurora Tasks application contract v1

AT-01 contract,8 November2026. Applies to the selected local application release,
not a full Aurora port. [Plan](../planning/aurora_tasks_release.md) and
[ADR0074](architecture-decisions/0074-native-application-job-authority.md).

## Identity, data and roles

The owned package is `dev.aurora.tasks`, selected useful release0.2.2, native addon
`mp_aurora_tasks`, numeric native version`19.0.0.2.2`. Candidate0.2.0's admitted
archive remains immutable: runtime qualification found inactive-member validation
needed correction. Candidate0.2.1 corrected that but exposed pending native list/
stage values being read through SQL before flush. Preserve both admitted archives;
neither is the release artifact. This local identity is not
a claim of publisher authentication or DNS ownership. Core47 remains sealed;
native job support was qualified on candidate48; the closed populated47 adoption
adds operator/recipe support in the selected final core49 (ADR0077). Neither
candidate replaces the sealed47 kit. Keep native list/form screens and native WebClient services. Optional
custom pages remain supported but no new custom Tasks page or Canvas expansion.

Lists own stages and list-bound tasks. No standalone tasks or workspace conversion.
Preserve existing record IDs, ownership, membership, assignment, dates and stages.
An existing NULL stage means open. New lists receive open and done stages; upgrade
adds missing open/done choices without replacing existing stages or task values.
Completion means the selected stage has`done=True`. Complete/reopen native actions
require current task write access and select only a stage of that task's list;
an external assignee needs no permission to browse/configure the list or stages.
Reject changing the `done` meaning of a referenced stage or deleting a referenced
stage. Create a different stage instead. This selected stability rule replaces
the old slice's unrestricted referenced-stage mutation; test its upgrade behavior.

| Actor | List/stage authority | Task authority |
| --- | --- | --- |
| Owner | Read/edit; manages membership, archive and list deletion | All tasks in own list |
| Member | Read/edit list and stages; no membership/archive/list deletion | Read/create/edit/delete tasks in member lists |
| External assignee | No list or stage-config access | Read/edit/delete assigned task; complete/reopen without list access |
| Creator no longer in list | No new list authority | Existing own task read/edit/delete, as original slice |
| Outsider | Denied | Denied unless creator/assignee as above |

Only active internal users may be assigned or added as members. Preserve immutable
creator/owner, no task/stage moves across lists, and the existing task archive rule:
current assignee, or creator if unassigned. Assignment and archive changes remain
separate operations. Native ACLs/rules enforce authority; UI hiding is not security.
Workspace selection neither grants nor removes native application permissions.

## Reminder behavior

1. Reminders are opt-in per task: none, at due time,15minutes before,1hour before,
   or1day before. Store due time in UTC; native UI uses the user's timezone. Require
   due time and active internal assignee when explicitly enabling a reminder.
2. Compute the absolute occurrence from due time and lead interval. The existing
   queue admits occurrences no more than30days ahead, with a24hour validity window
   and a separate30second attempt budget. Reject explicit reminder scheduling
   outside that horizon or already beyond its validity window with a useful
   validation message. Long-future tasks remain valid without reminders. No
   rolling producer or automatic extension beyond this supported window is implied.
3. Queue transactionally with task changes. Changes to due time, reminder choice,
   assignee, completion or task/list active state invalidate the old occurrence.
   A protected monotonic revision identifies each new occurrence. Name/description
   edits preserve that occurrence; delivery snapshots the current title/due time.
4. Complete, archive, remove reminder, unassign or delete cancels pending/running
   database delivery under the same task authority. Queue cancellation and business
   state commit together. Reopening or reassignment creates a new occurrence only
   while its window is still valid; otherwise show expired/unscheduled status,
   allowing the task workflow to continue. A user may choose a new due/reminder.
5. Each occurrence belongs to its originating human. Enqueue, preparation and fenced
   apply require that person's active internal identity, active native installation,
   current release and current task access. Revocation blocks delivery; a later
   authorized edit may create a new occurrence. Never fall back to a service admin.
6. Apply locks/rechecks the current task revision, assignee, due time, completion
   and task/list active state. Check current recipient activity and task read access.
   Stale, completed, inactive or superseded work produces no notification. Current
   authorization, revision and queue cancellation fences must hold at commit.
7. The effect is one recipient-private database notification per task/revision,
   committed atomically with job completion. Unique storage plus fencing prevents
   duplicate effects on retry, interrupted workers or repeated submissions. This
   does not claim exactly-once process execution or external delivery.
8. The native inbox displays a title/due snapshot and read/unread state. Recipients
   can read/mark only their notifications. No ordinary create/delete or arbitrary
   notification mutation. Opening the task rechecks current task access. Historical
   notifications retain their authorized-at-delivery snapshot after reassignment
   or task deletion; they do not confer renewed task access. No descriptions or
   private queue context are copied into notifications.
9. Expose a useful reminder status on authorized task screens: disabled, queued,
   sent, cancelled/obsolete, expired or blocked. Do not expose private payloads,
   actor credentials or operator controls. Failed/missed delivery must not appear
   as a successful notification. No latency guarantee when workers are stopped or
   capacity is exhausted. Initial profile includes an urgent managed lane; bulk
   work retains its separate pool.

## Native job adapter v1

`JobDefinition` explicitly declares`authority='native'`, owning`addon`, managed
pool and empty workspace service/API/method fields. Workspace definitions keep
their existing service binding checks and cannot use the native submission path.
`native_jobs.enqueue_scheduled(env, ident, values, key, schedule=..., version=1)`
uses the non-sudo originating user and registered definition. A real installed
site-scoped native package and matching installed native version are mandatory.
Only identity mapping may be provisioned; it grants no membership, role or access.
V1 native submissions are human-origin only; technical submissions keep the
existing credential-bound workspace API.

Private queue rows use a NULL workspace, original principal and actual native
installation. Use NULL-safe identity/deduplication, distinct native-installation
and workspace claim/compute partitions, and bounded fair selection in the same
managed worker fleet. Saved payloads contain no selectable backing user, role or
grant. Reconstruct from stored actor metadata, and check current native ACLs/rules
at preparation and fenced apply. Workspace history/status APIs must not reveal
native rows. Native cancellation by a task editor must authorize the stored job's
resource through its fixed registered definition under that current editor before
changing queue state; no caller-provided authorizer or serialized permissions.

Reuse existing dispatch pause, claim generations, detached compute limits,
heartbeat/deadline, retries, retained identity, drain and checkpoint controls.
Native v1 does not add native domain-event subscriptions, recurring schedules,
external effects, continuations or technical-origin authority. Add them only when
an application needs their separately defined contracts. Existing workspace APIs
and their qualified profiles retain their declared scope.

## Owned application authoring recipe v1

A data-only local TOML recipe selects`schema_version=1`, `manifest`, `addon` and
`resources` (archive path to source path). All input paths are portable, relative
to one explicitly selected source checkout and free of source links/junctions.
The addon directory name and native/package versions must match the normalized
manifest. Read source as bytes; never import it or run build hooks. Include
explicit application license/provenance notices and required schemas/assets;
resources cannot replace native code, manifest, inventory or provenance. Bound
sizes/counts and run the existing archive validator. Native dependencies must
resolve to admitted framework addons or reviewed application packages when the
distribution is composed; archive construction alone proves no dependency closure.

Archives use the existing owned R1 `.mplug` layout, canonical portable paths,
fixed timestamps/order/modes and source/inventory hashes. Historical native ABI
labels/prefixes do not imply external Odoo addon compatibility. The local builder
supports native applications; external worker metadata keeps its separate authoring
path. An unsigned structural preflight never grants curated trust or installation.
Return the exact digest for independent review/catalog admission; never overwrite
an existing output or reuse a version for different bytes. Build/release inventories
must consume the reviewed archive bytes and bind application artifacts/dependencies.

## Release and recovery

Support clean install and the concrete populated native0.1.0 app on sealed core47
to the selected0.2.2 app/foundation successor. Initial adoption of package metadata
for the previously native-only app must be explicitly reviewed and preserve rows;
do not pretend it is an ordinary already-registered plugin upgrade. The known
registered candidates0.2.0/0.2.1 also have explicit non-destructive migration
declarations to0.2.2; never replace their archive bytes in an existing catalog.
These declarations do not claim their foundation updates were qualified. First release
qualification must specify this closed adoption/upgrade path, exact source/target
images, application artifact/dependencies, installed states and data witnesses.
Reject unselected sources or changed native/artifact inputs before mutation.

Existing tasks upgrade with reminders disabled. No inference from due dates and
no unsolicited historical notifications. Preserve list/stage/task/member data and
roles. New notification/occurrence metadata has explicit retention and a tested
rollback disposition. Restore into a fresh independent checkpoint database with
the original image and current independent operator authority; traffic remains
closed until a separately reviewed resume. Reconcile queue generations so stale
claims cannot apply after restore. A restored notification is a database effect,
not an external delivery; no external provider ambiguity is introduced.

Qualify both failed app recovery and a still-useful Maintenance peer. Final-image
tests cover fresh install, populated adoption/upgrade, native role denials, actual
reminders/edits/cancel/retry, mixed partition managed execution, browser inbox and
completion, source reproduction/privacy and exact owned Docker retirement. The
AT-01 source-overlay probe is feasibility evidence, not any of these release passes.
