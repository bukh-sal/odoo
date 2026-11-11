# Application capabilities and deliberate boundaries

The core exists to enable useful independent applications. A limitation requires
a reason and an owner; an untested path is not labelled impossible. Application
acceptance includes actual visible interactions as well as data, authorization
and lifecycle behavior. Source checks and backend-only results cannot establish
that a screen is useful or usable.

| Requirement | Current state | Reason / next evidence |
| --- | --- | --- |
| Own models, views, app assets, service schemas and events without a domain branch in core | Demonstrated by independent Partners on provisional0.2.1 | Keep business code and presentation in independently packaged apps. Record any genuine general gap in the core-change ledger before changing core. |
| Stock forms, native lists, workspace selection and revision-aware saves | Demonstrated in a real browser | Apps still own business concurrency semantics; repeated form-adapter work is a possible general usability improvement, not a reason to drop conflict protection. |
| Rich app-owned boards, configurable workflow stages and contextual task panels | Available extension mechanisms; independent clean-candidate application qualification in progress | Native client actions/assets and declared app-to-app integrations are the intended paths. No mandatory reference shell or core model-specific branch. Judge actual keyboard, loading, error, empty and populated states. |
| Model extension and app-to-app navigation/data links | Declared dependency/extension mechanisms exist; richer independent combination needs qualification | Use an explicit optional integration package. The core must not acquire knowledge of a customer, project or task model. |
| User-defined stages | Application responsibility, not an engine limitation | A three-state demo is not a permanent restriction. The app must define completion semantics and test referenced-stage changes, history and reminders. |
| Assignment to current team members | App responsibility with current identity/membership checks | Workspace membership administration remains admin-only. A bounded app directory must not expose account credentials, inactive users or members of another workspace, or elevate callers to make assignment succeed. |
| Background reminders and event consumer effects in a new application | Unproven until installed qualification | Exercise current actor/resource authority, rescheduling, cancellation and duplicate handling. Do not call a displayed reminder field a delivered reminder. |
| Arbitrary model changes and populated migrations | Explicit migrations supported; not universally qualified | A real application migration must preserve useful data and recover under current authority. Existence of a migration declaration earns no acceptance. |
| Trusted native Python and same-origin frontend extensions | Intentional R1 trust boundary | Native code shares the process and can execute privileged logic. Permissions and manifests do not sandbox hostile code. Isolation is a separate R2 requirement. |
| Hot-unloading native code or independent native versions in one shared process | Intentionally unsupported | Python imports/process hooks and native registry/schema lifecycles require an immutable image and controlled transition. Feature suspension, database uninstall and source removal are distinct operations. |
| Arbitrary third-party addon compatibility, stable ABI and LTS | No promise in provisional0.2.1 | Support covers exact qualified combinations. This owned fork preserves its supported contracts and data/recovery guarantees, not external upstream compatibility for its own sake. |

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
