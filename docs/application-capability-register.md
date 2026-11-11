# Application capabilities and deliberate boundaries

The core exists to enable useful independent applications. A limitation requires
a reason and an owner; an untested path is not labelled impossible. Application
acceptance includes actual visible interactions as well as data, authorization
and lifecycle behavior. Source checks and backend-only results cannot establish
that a screen is useful or usable.

| Requirement | Current state | Reason / next evidence |
| --- | --- | --- |
| Own models, views, app assets, service schemas and events without a domain branch in core | Demonstrated by independent Partners and the bounded Workboard workflow on provisional0.2.1 | Keep business code and presentation in independently packaged apps. Workboard adds16 app-owned inventory entries and preserves all3682 standalone-core inventory files. Its event delivery is not newly qualified. Record any genuine general gap in the core-change ledger before changing core. |
| Stock forms, native lists, workspace selection and revision-aware saves | Demonstrated in a real browser | Apps still own business concurrency semantics; repeated form-adapter work is a possible general usability improvement, not a reason to drop conflict protection. |
| Rich app-owned boards, configurable workflow stages and contextual task panels | Workboard0.1.1 desktop workflow demonstrated on core0.2.1 | Actual browser create/comment/custom stage, drag plus reload, select alternative, search and archive/restore passed. Visual review caught a malformed draggable attribute in0.1.0; app-only0.1.1 fixed it through normal image/approval/upgrade. No mandatory reference shell or core branch. |
| Model extension and app-to-app navigation/data links | Declared dependency/extension mechanisms exist; richer independent combination needs qualification | Use an explicit optional integration package. The core must not acquire knowledge of a customer, project or task model. |
| User-defined stages | Application responsibility, not an engine limitation | A three-state demo is not a permanent restriction. The app must define completion semantics and test referenced-stage changes, history and reminders. |
| Assignment to current team members | Workboard implements a bounded app-owned read-only directory; installed assignment and foreign-member refusal demonstrated | The existing membership-management API remains admin-only. Workboard uses trusted native fixed scoped reads, not sudo or relaxed management access. A reusable read-only directory service is a possible general improvement if other apps need the same policy; it is not currently a ready-made frontend API. No credentials or inactive/foreign members are exposed. |
| Personal-private tasks or per-list secrecy | Not implemented by Workboard; application policy choice | Current tasks are workspace-visible team work. My work filters assignment and does not promise privacy. Implement and test a separate ownership/sharing policy before adding a private mode; do not disguise missing policy as a platform impossibility. |
| Due date/time wire representation | Intentional existing UTC-Z protocol; local-time browser entry demonstrated | The UI converts local input to canonical UTC and displays it in the current time zone. An initial test offset timestamp was correctly rejected before task creation; correcting the test required no core/app change. This does not establish recurring reminders or time-zone travel behavior. |
| Background reminders and event consumer effects in a new application | Unproven until installed qualification | Exercise current actor/resource authority, rescheduling, cancellation and duplicate handling. Do not call a displayed reminder field a delivered reminder. |
| Arbitrary model changes and populated migrations | Explicit migrations supported; not universally qualified | A real application migration must preserve useful data and recover under current authority. Existence of a migration declaration earns no acceptance. |
| Trusted native Python and same-origin frontend extensions | Intentional R1 trust boundary | Native code shares the process and can execute privileged logic. Permissions and manifests do not sandbox hostile code. Isolation is a separate R2 requirement. |
| Hot-unloading native code or independent native versions in one shared process | Intentionally unsupported | Python imports/process hooks and native registry/schema lifecycles require an immutable image and controlled transition. Feature suspension, database uninstall and source removal are distinct operations. |
| Arbitrary third-party addon compatibility, stable ABI and LTS | No promise in provisional0.2.1 | Support covers exact qualified combinations. This owned fork preserves its supported contracts and data/recovery guarantees, not external upstream compatibility for its own sake. |
| Viewer empty states and responsive interaction | Desktop viewer read/no mutation controls demonstrated; copy polish and mobile remain open | Some empty-state copy suggests actions unavailable to viewers: an app-owned UX repair, not an intentional restriction. The requested390px browser override remained1422px, so no mobile acceptance is claimed. Return with role-specific copy and an actual narrow-width interaction check. |

The [bounded work-application evidence](evidence/G7/20261111-work-application-01/qualification.json)
records source, installed, visual and unproven scopes separately. This is a
useful team-work first slice, not full customer/project/reminder product parity.

For each next application, retain a short decision record containing the user
journey, observed interaction, capability status, rationale, tradeoff, repair
owner and next qualification. Use these statuses: **demonstrated**, **intentional
boundary**, **gap to repair**, **unproven**, and **application choice**. Temporary
scope choices must have a reason and a return condition; they are not platform
limitations by default.

Visual reviews should follow a realistic create/find/edit/complete/reopen flow,
check clear ownership and status, visible loading/error feedback, keyboard
alternatives to dragging, discoverable actions, retained drafts and useful
context. Reference products can inform these requirements without embedding
their private code, branding or business model in core.
