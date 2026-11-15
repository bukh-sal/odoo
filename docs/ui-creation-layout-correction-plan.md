# Installed creation layout correction

Activated15November2026 after core31/config5 on the isolated18730 cohort.
This is the prerequisite for accepting the active creation slice, not another
feature or a replacement for UI-D03 through D06.

Actual native fullscreen has `o_modal_full` and retains the same input IDs/draft,
but its content remains980x301 in a1363x789 viewport. The old Dialog fullscreen
geometry is limited to small media. Organization sheet has correct704px logical
end placement but inherits28px vertical `.modal-dialog` padding, leaving its
content733px high at y28 instead of meeting the viewport edges. Private screenshots
and geometry are retained under `.local/ui-create031-browser-01`. No runtime CSS
was injected. Normal validation, dirty close/Keep editing/Discard, zero-effect
cancel, actual person/org saves, durable reader and full-page route passed.

Make the existing `.mp-record-create` opt-in own its fullscreen geometry at every
screen width. Add screen-only rules for modal-dialog width/height, zero margin /
padding and full-height content/body scrolling. Remove inherited vertical padding
only for the existing opt-in sheet. Keep normal Dialog, form/model/authority,
mounted draft, native focus and print rules unchanged. Disable drag offsets while
fullscreen; retain normal centered-dialog dragging outside that state. Use logical
properties and existing tokens. No new component, overlay service or business
registry. The default native compact creation can use the existing md size650px
instead of lg980px; custom author-supplied size remains respected. Fullscreen is
still the same mounted form, never save-and-navigate.

Reserve provisional core/web/native0.2.32 for these shipped changes; all five
currently installed archives remain byte-exact. Verify the actual pinned Sass/RTL
compiler, non-screen declaration identity, native props/template and actual Owl
draft/guard regression. Then ONE immutable normal app-enabled core32 build and
all-layer audit, exact populated core_upgrade plan/review/approval/checkpoint/apply
on18730 only. Preserve current two new partners, task, pending reminder/job,
original customer/task/218B brief/pin, business history and current authority.
Never replay completed31 operations or touch main18610/human/new.

Installed proof must measure compact dialog, desktop fullscreen and sheet edge
geometry; expand/return/resize/Escape must retain the same draft with zero writes.
Check narrow390, dark and logical RTL; retain original UI matrix and final
canonical work. An already-pending reminder is not delivered merely because its
row exists: use the normal current native job operator if a delivery proof is
performed, without clock or queue edits.

The composite form also briefly shows retry-only guidance during an in-flight
reminder request. That is a real app-owned presentation finding, not a failed
task/reminder effect. Correct it in the next coherent Workboard successor with
its own version/archive and actual pending/partial-state proof; do not relabel the
installed2.18 archive or broaden this core maintenance operation. Informational
record composition starts only after this active creation prerequisite is closed.
