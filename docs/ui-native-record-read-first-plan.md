# Native read-first records and focused warnings

Activated15November2026 after installed core19/Partners1.5 review against
Meridian partner360. This is the next coherent D05 refinement, under the same
D03-D06 goal. It deliberately changes one inherited interaction choice: normal
existing native records should open for reading, with an explicit Edit command.
Task/Document screens already separate reading and editing. An always-open edit
form is not a compatibility requirement of this owned fork.

## Current evidence and problem

Core19/config15 fixed navigation's intrinsic sizing and dark section boundaries.
Partners1.4's actual flat col4 layout was rejected;1.5/config17 uses two ordinary
native inner groups, measured496.463px each at1363px and stacked at390px. Names
wrap, revision stays loaded/invisible, normal explicit Notes Save advanced one
owned Sample revision2→3. A stale save got fixed safe guidance, kept an unredacted
Notes witness until explicit Discard, and produced no extra commit/event. Other
165partners/17tables/full prior history and ten other sites remain exact.

The current reader is still visually dominated by editable fields, unlike
Meridian and our custom apps. The simple native warning uses xl1140px despite
short guidance. Custom Workboard's browser title also falls back to Odoo; that
belongs to its existing app action displayName convention, not a core branch
knowing business app names, and is queued for the next app-owned batch.

## Source design, before implementation

1. Use the existing Record mode machinery. For normal full-page FormController
   with record ControlPanel and standard persistence, existing records initially
   use readonly; New starts in edit. Explicit readonly, disabled control panels,
   embedded/custom persistence callbacks and in-dialog forms preserve their
   current contracts. Keep props/state/input objects and existing activeActions.
2. Add one named primary Edit button only when that normal reader can edit.
   Entering edit calls the existing model.root.switchMode; it is a presentation
   change, not authority. Native write guards/current revision CAS still decide
   every mutation. Preserve scope and field data; no extra auth policy/cache.
3. Explicit successful Save returns the same current existing record to reading.
   Refused/error saves keep edit mode and draft. Explicit Discard returns an
   existing record to reading; a new record retains normal abandon/history logic.
   Preserve custom callbacks and don't switch a different/destroyed controller
   after navigation. Keep native leave/visibility/unload save behavior; this is
   NOT a manual-save-only promise. Existing view action buttons retain semantics.
4. Use existing FormStatusIndicator callbacks. Add an optional clean-editing
   presentation so entering Edit without typing offers Done/Cancel and truthful
   Editing state. Dirty/invalid/new/pending modes retain Save changes/Discard,
   validity and duplicate guards. Legacy callers without the optional prop are
   unchanged. No second persistence path or new framework/registry/export.
5. New and record traversal need explicit modes in the eligible reader: New
   remains editable, successful navigation goes to reading, refused navigation
   keeps the same draft and URL. Preserve loaded-ID count, FetchRecordError and
   existing save/load producers. Restored modelState must not lose its draft.
6. Focus first usable sheet input after explicit desktop Edit; return to Edit
   after explicit successful Save/Discard. Use requested-transition flags and
   Owl effects, not a polling/timing helper. Do not steal focus from a dialog,
   unrelated element, destroyed/replaced record or touch/disable-autofocus flow.
7. Set only ordinary WarningDialog to existing medium size. Keep task/technical
   dialogs, error redaction and recovery text unchanged; test actual wrapping,
   close/Escape/focus in desktop/narrow light/dark.

Reserve provisional local core0.2.20/mp_core19.0.0.2.20/web19.0.2.20.0. Keep all
five exact app archives/Python/locks/authority/schema/freeze byte-identical. No
app IDs, fake metadata, runtime CSS/source injection or new dependency.

## Verification and execution

Test actual controller initial-mode producer, eligibility matrix, New, save/
discard/refusal/error/pager, state preservation and focus requests; actual status
component default/clean/dirty/invalid/pending/duplicate behavior. Preserve table,
router and app CAS regressions. Mount affected real Owl components with the real
button executor; compile changed templates and pinned Sass/RTL. Prove predecessor
fails the new reader witness. Then affected native/staging/identity checks/freeze.

One immutable clean image, exact expected shipped delta/no new exports/unchanged
five apps/Python, final-layer audit. Normal independently reviewed10scope core
upgrade, checkpoint, exact hash approval/apply; reload fresh observer. Bind current
Sample82revision3/all166partners, other17tables/full history/ten other targets.
No replay of core19 or any app operation; old evidence stays immutable.

Installed checks: normal reader text/no editable fields; keyboard Edit/focus;
clean Done/Cancel with zero writes; one separately journaled useful edit only if
needed; dirty save/discard/stale refusal; New editable/cancel without orphan;
loaded record traversal; native-viewer/forcedreadonly/dialog controls; meaningful
related task/document route; desktop/narrow/light/dark. Scope any actual writes
to an owned Sample record with fresh exact intent and verify effects/retention.

Then finish the original RTL/real200%zoom/motion/contrast/current-authority/
optional-app matrix and one final frozen canonical. Do not start another full
suite while this interaction source is still being refined. No formal a11y,
production/publication or broad support claim; original UI0of4 until cards pass.

## Pre-approval general-layout counterexample

Candidate0.2.20 was built/audited/staged and an unregistered proposal prepared,
but was NOT approved/applied. A real Owl/native field witness with a standard
form content region and no sheet exposed a focus defect: the first-field selector
required `.o_form_sheet`. The framework supports such forms; that accidental
restriction is not intentional. Preserve its candidate/proposal and failing log.

Reserve unpublished0.2.21/core19.0.0.2.21/web19.0.2.21.0 for the corrected
successor. Scope focus to the existing `.o_content` region, covering both sheet
and ordinary native form layouts. Keep every other mode, callback, guard and
dependency byte unchanged. Prove the no-sheet witness red on20/green on21 and
retain the sheet proof; source/component/identity checks, fresh clean image,
normal new stage/proposal/approval/maintenance only. Never register the retired
20proposal2600d4ca-d643-4f78-888d-9b75a591ae79. Main stays config17/core19 while
preparing; no uncertain write/recovery or live patch exists.
