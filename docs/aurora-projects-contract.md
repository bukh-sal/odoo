# Bounded Projects application contract

Frozen9November2026 for AP-I..L. This defines an owned native application and a
separate optional integration. It is not a full Aurora import or an external
addon compatibility promise. Native WebClient/list/form/search/action handling
is the default; no custom shell, page, dialog or notification infrastructure.

## Source selection and bounded workflow

Read-only Aurora `bedrock-2.2` commit
`e48e04ed4cf155a83e66e08dfb33a669ebb5c228`:

| Candidate | Observed source | Decision |
| --- | --- | --- |
| Projects | `Projects/models.py`:name128,description,protected manager,five states,optional customer/logo. API view/serializer files are empty;tests/views are placeholders. `Bedrock/media.py` has a manager/customer-based logo predicate,not general Project CRUD authorization. | Select the small planning/lifecycle workflow;define new explicit native roles and tests. |
| Partners | `Partners/models.py` includes customer/vendor/lead/contact data;API imports permissions,cloud folders/files,logs,reports and timelines. | Defer the broader CRM/storage/reporting decisions and real-data migration. |
| Maintenance | Retained foundation application already qualified with native workflows and independent deployment. | Keep as a useful peer;the new phase proves another independently authored package. |

Everyday scenario:an owner plans an inspection project,assigns its manager,
shares read access,activates/holds/completes/reopens it,and optionally links
existing Tasks. Version0.1.1 adds an optional target date and native late-project
filter:planned work needs an explicit deadline beyond a task's reminder time.
This is a selected application addition,not a foundation/schema change invented
for testing. Initial0.1.0 remains a useful lifecycle app and a recovery baseline.

Exclude customer/logo,Partners/accounting/chat/cloud imports,attachments UI
expansion,budgets,timesheets,subprojects,notifications and new job handlers.
Use existing native attachment support only as an owned recovery witness.

## Package and data identities

- Separate source repository:`aurora-projects`;package`dev.aurora.projects`,
  native addon`mp_aurora_projects`,site-native activation only.
- Platform pin`==0.1.49`;native dependencies`web`and`mp_core`only. No Tasks,
  workspace,service binding,technical principal or grant dependency.
- Model`mp.aurora.project`:name(required,trimmed,1..128),description(Text),
  owner_id(required,readonly,current-user default),manager_id(required,
  active internal user,current-user default),member_ids(active internal users),
  status(required,default planned),active(default true). Native audit columns
  remain native. Owner is always assigned by the server and immutable.
- Native/package versions0.1.0→`19.0.0.1.0`,0.1.1→`19.0.0.1.1`.
  Version0.1.1 adds nullable`target_date`(Date);existing records mean unknown
  date,not an invented deadline. Native ORM adds the column;no migration script
  or destructive backfill. Declare only registered0.1.0→0.1.1/checkpoint/restore.
- Readonly user-context permission booleans may support native form attributes;
  they never authorize writes. Generic text edits retain native last-save-wins;
  do not claim revision tokens or edit history. Lifecycle/role writes lock and
  recheck the current project before mutation.

## Current native authority

Every operation requires the actual installed site-native package and active
internal user,using existing native availability/ACL/rule infrastructure. Native
principals do not grant project access. Do not switch user or use sudo to make
ordinary workflows succeed.

| Actor | Read | Business/lifecycle edit | Sharing/archive | Manager transfer | Delete |
| --- | --- | --- | --- | --- | --- |
| Owner | yes | yes | yes | yes | yes |
| Current manager | yes | yes | yes | no | no |
| Member | yes | no | no | no | no |
| Other active internal user | no | no | no | no | no |

Any active internal user can create their own project. Forged owner values cannot
choose another owner. Manager/member choices must be active internal users.
Membership/manager changes affect current access;archive affects default lists,
not ownership or historical access. Native form controls reflect read-only member
access,but direct RPC/server denials remain mandatory. Ownership cannot be moved.

New records start planned. Allowed status transitions,checked against the current
locked state through native object actions and direct writes alike:

`planned→active/cancelled;active→on_hold/completed/cancelled;`
`on_hold→active/cancelled;completed/cancelled→planned`.

Repeating the already-current state is harmless. Other transitions fail without
partial writes. Authorized members may read archived records explicitly;only
owner/manager may archive/unarchive. Manager transfer remains owner-only.

## Optional Projects–Tasks integration

Separate repository`aurora-projects-tasks`,package
`dev.aurora.projects_tasks`0.1.0/addon`mp_aurora_projects_tasks`19.0.0.1.0.
Site-native only,hard package dependencies Projects`>=0.1.0,<0.2.0`and
Tasks`==0.2.3`;native dependencies both matching addons plus framework core.
Qualify both Projects0.1.0/0.1.1. Both base apps work without this extension.
Optional means a separately selected/installed deployment package,not hot unload
or an unqualified global suspension/removal switch.

Own model`mp.aurora.project.task.link` contains required project_id/task_id,
optional note and a unique pair constraint. Declare Project extension fields
for filtered links/counts and native view inheritance explicitly;no Task model
or core field is replaced. Pair identity is immutable after creation.

- Read/search/count/display/Open task require both current Project and Task read
  access,not simply knowledge of a foreign ID. No links,counts,titles or related
  IDs may leak when either resource is unreadable. Search/rule filtering must
  apply before native name/display/group operations expose data.
- Create/note edits/explicit unlink require both resources'current write access;
  a Project read-only member with Tasks edit rights cannot link on that basis.
  Check real base models'ACL/rules as well as the version-bounded link rules.
- Lock/recheck relevant Task/list and Project authority rows for mutations,
  following existing Task→list ordering. No grants or serialized permission
  snapshots. Package availability must be current for all three packages.
- New links require active records. Project/Task deletion may cascade their owned
  associations;it never deletes or grants access to the other business record.
  Historical links to archived records remain readable with current rights.
- Native Project form opens native link forms/actions and native Task forms.
  Use existing action/dialog/view hosting,not a new frontend route or renderer.

## Qualification and recovery

Freeze [ADR0080](architecture-decisions/0080-independent-application-set-composition.md)
before implementing new-slot composition. Prove data-only assembly,dependency/
ownership/version/core-drift refusals and actual ordinary native planning before
substantial app implementation. Keep AP-I unpassed until real feasibility evidence.

AP-J requires actual native create/defaults/roles/transitions/archive/member
read-only behavior and direct denials. AP-K requires both-resource positives,
member-write refusal,asymmetric access/search/count/Open denials and current
revocation. Use native browser workflow on final selected source/artifacts.

AP-L requires a clean Projects-only installation with Tasks/extension absent,
a useful populated full app set,unsupported dependency/version refusal before
mutation,and actual0.1.0→0.1.1 evolution. On a disposable full-set sibling inject
post-publication failure,stop failed app,independently restore original app/data/
files into a fresh database,retain current native authentication revocation,
separately resume,and perform useful native/cross-app work before fresh forward.
ADR0079's updated host operator is required when native jobs are present.

Application-owned role relationships restore to checkpoint;there is no generic
post-checkpoint application-ACL overlay. Current platform/native authentication
authority retains its qualified reconciliation. Unknown external effects remain
refused. Preserve the working Tasks pilot and all sealed foundation artifacts.
