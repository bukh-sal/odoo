# Author-selected record creation

Activated15November2026 at2770c51b144 after the real core30 customer/task/document
journey. This is the next section of UI-D05 in the existing delivery goal; UI-D03
through D06 retain every original acceptance card. The eight-addon default,
private application boundary and protected demonstration sites stay intact.

## Current evidence and design

ListController.createRecord delegates non-inline creation to the action service;
its callback currently always calls openFormView(false). Row selection separately
uses openFormView(recordID). Native FormViewDialog already resolves the selected
native form, including the application's js_class/model, fields, validation and
save callback. Its existing expand callback saves before navigation. The model's
exportState exports configuration/caches, not a transferable unsaved record;
therefore do not call it a lossless draft transfer.

Use a small creation-specific component over FormViewDialog and the existing
Dialog/focus service. Author choices are explicit action context:

| Option | Meaning |
| --- | --- |
| create_surface absent | Existing native creation behavior, including editable lists |
| create_surface=page | Native full-page creation route |
| create_surface=dialog | Native form in a centered dialog, directory retained |
| create_surface=sheet | The same native form in a logical-end sheet, directory retained |
| create_form_view_ref optional | Dialog/sheet-only native form reference; page uses the action's declared form, and existing-record detail keeps its ordinary form |

Reject unknown values before opening anything. No automatic field-count rule,
model/app ID branch, new ORM, alternate permission root or universal business
workflow registry. The View service continues resolving real native form and
application model overrides. Presentation grants no write permission.

Expansion makes the **same mounted form fullscreen** and can return it to its
initial surface. It performs no save, action navigation, serialization or URL /
browser-storage write. Authors choose page initially when the creation workflow
needs a dedicated route. A completed record still has its ordinary durable detail
route. Document this distinction instead of advertising an unsaved URL.

## Core implementation

1. Add a neutral record-creation helper and creation-specific FormViewDialog
   subclass under web/static/src/views/view_dialogs, included by the existing
   native asset glob. The helper delegates page to the existing action callback;
   dialog/sheet use the standard dialog service. The action service supplies the
   action model, declared form view, current native context and title. Row-open
   routing is unchanged. ListController provides a post-save reload of its
   current model, retaining filters/grouping; absence of policy keeps old inline
   behavior, while an explicit policy wins over inline creation.
2. Expose one optional native FormController onRecordReady callback and an opt-in
   preventAutoSave presentation prop. The callback reports its actual current
   root on mount/change and clears on teardown. Default behavior remains exact.
   Creation-specific forms suppress visibility/unload/leave-triggered saves;
   dirty unload warns and the ordinary global leave hook asks before discarding.
   The new dialog's header X/Escape/Cancel all use one async close decision. A
   guarded Dialog subclass must not rely on the base dismiss return value, which
   closes after data.dismiss regardless of a false return. Existing dialogs are
   unchanged. Use record.isDirty to flush pending field edits before deciding.
3. Explicit Save runs the actual record.save once, using the selected native
   model and server validation. Prevent double submit/close during save. Dirty
   close offers Keep editing / Discard draft. Validation failure retains the
   form. A successful create followed by a list-refresh failure is labelled
   created; it must never run another create. Connection loss/abort is a
   conservatively uncertain native outcome: retain draft, disable blind create
   retry and explain that the directory must be checked. Closing cannot undo a
   possibly committed record. Keep normal backend scope/revision/ACL guards.
4. Use shared tokens, logical sheet placement, a bounded desktop width and full
   narrow width, native focus trap/Escape/scroll, clear title/actions and reduced
   motion. The native form's footer buttons remain actual controller actions.
   Fullscreen toggles the wrapper only. Add no library/download. Check actual
   backend/frontend/minimal asset closures against the native asset consumer;
   no repeat of core29's missing frontend import. No base RNG or DB schema edit
   is needed because action context already carries author presentation intent.

## Real application demonstrations

Partners successor0.1.8/mincore31: Overview retains page creation; People opts
into dialog; Organizations opts into sheet. Add one creation-only compact native
view with name/email/phone and necessary hidden defaults/revision. Keep its
existing PartnerFormModel and durable informational detail/Edit intact. Preserve
existing records and all service/security declarations. New immutable archive.

Workboard successor0.2.18/mincore31: enrich actual task creation with an optional
personal reminder in the same experience. Reuse its existing idempotent create
and reminder_set services. Validate reminder input before the first mutation;
bind the actual returned task identity/revision, then schedule separately. Keep
separate immutable submission keys and explicit phases. If the reminder fails,
show that the task exists; retry only the reminder (same intent when uncertain),
or finish without it. Freeze task fields after confirmed creation. Closing never
pretends to roll back the task. Preserve editing/list/stage behavior and all
authority checks. Correct the already-observed app-owned rail/priority icon
metadata while editing those same UI files; no new icon registry or app branch
in generic Shell. No finance feature or transaction-atomicity claim.

## Verification and delivery

- Focused actual-method tests for page/default/inline delegation, policy refusal,
  exact action/context/form selection and existing-record routing. Actual mounted
  Owl/dialog/native form boundaries for three presentations, required-field
  refusal, dirty Cancel/X/Escape, save busy, uncertainty and refresh-after-save
  failure. Fullscreen must retain the same input/model and emit zero writes.
- Native lifecycle regression proves opt-in prevents automatic saves and default
  legacy behavior stays intact. Use the actual native asset resolver/compiler
  and pinned Sass/RTL; inherited application form model must survive. Preserve
  the installed breakpoint old-failure/new-source regression.
- Private Workboard tests exercise real orchestration success and task-created /
  reminder-failed, uncertain replay, cancellation, duplicate clicks and authority
  denial. New package version/digest; current other four/three archives retained.
  These source boundaries are not installed proof.
- Deliver through immutable normal builds/stage/review/checkpointed apply on the
  owned18730 cohort. Core step retains all five current app archive pins; app step
  admits only the two new archives. Verify source maps/Python/archive identities,
  existing customer/task/218B brief/pins/authority/full job/outbox business history
  and checkpoint files. Reload target/observer after replacement. Never replay a
  completed apply or modify the human-controlled main18610 form.
- Actual in-app checks: People dialog, Organizations sheet, Overview page;
  successful create leads to ordinary durable reader; cancel creates no record;
  fullscreen retains draft without saving; related task/reminder success and
  honest partial outcome; desktop/narrow/light/dark/RTL/keyboard and source31
  breakpoint-only reflow. Show useful screenshots and critique. Backend/session /
  current-authority and optional-app cards remain required at final integration.

Core31 is reserved but unpublished and can carry this coherent delivery before
another image. New reader/backend changes outside owned web presentation are not
authorized by this plan; report any exact maintenance refusal rather than add a
bypass. Native standard ORM creation is not made idempotent by a dialog. Authors
needing retry-safe composite effects use existing application service contracts.
Freeze inventory review must confirm this additive native presentation API does
not silently change a frozen DTO or service contract. Record source/evidence /
limits, then write the informational-record composition plan at its own entry
using these findings. No publication/production, unknown deletion or cleanup.
