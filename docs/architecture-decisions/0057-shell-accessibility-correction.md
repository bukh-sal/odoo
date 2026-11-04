# ADR0057: correct measured shell accessibility defects

Date:2026-11-04. Status: accepted correction scope; installed qualification pending.
Active G-01b; spec17.4/UI09. No broader frontend rewrite or Canvas expansion.

Actual current14de/config4 UI09 observation found light subtitle contrast4.38
against required4.5; dark Members/native confirmation headings inherit black;
document language is unset even when the shell changes to Arabic RTL. Native
text fields/Labels textarea lack the shell's visible focus outline. The generic
button background shorthand also erases the existing Odoo close-button image.
Settings headings/help/labels remain English in Arabic mode.

Correct the owned shell presentation: slightly darken its muted light token,
apply foreground to all heading levels, preserve native button background images
by setting background-color, use Bootstrap's existing white-close filter in dark
mode, and extend the existing focus ring to text inputs/areas. Set an English
document default in the owned bootstrap and synchronize HTML language/direction
with the existing shell preference. Use the existing translation dictionary for
the visible Settings labels/help and their accessible names. Preserve native
Odoo View/action/dialog/notification/command behavior and the Labels HTML dialog.

The first harness omitted Enter's character event and expected Canvas reload
without its real discard confirmation. Corrected actual keyboard tests pass
Odoo confirmation focus trapping/restoration, Labels names/Escape/restoration,
Canvas keyboard lane change and explicit discard of local long-input changes.
The UA HTML dialog briefly reports BODY as active during Tab traversal, but
attempting to focus an inert background control fails; background app controls
cannot receive focus. Do not replace native modal behavior with another trap.
Canvas loses selection focus after a local move but remains keyboard operable;
retain this diagnostic observation for the final scope review, not product polish.

Use a single core24/Shell11 immutable code-only maintenance candidate, keeping
packaged plugin artifacts, SDK public contracts and Python/OS dependencies
unchanged (platform version0.1.24/nativecore19.0.0.1.24). Follow ADR0052 and the
ordinary independently reviewed core_upgrade, checkpoint and publication path.
No direct live source overlay. Existing106frozen files/eight rows must stay exact.
Before pass: actual candidate admission, installed native view/Labels/keyboard,
contrast including all headings/dialogs, focus rings/native close image, document
language/Settings names, RTL/narrow/equivalent200% reflow, preservation and
current source/asset/privacy/release binding. Physical screen-reader/browser
chrome zoom and locale-formatting scope must be reconciled, not silently claimed.

Revisit on upstream/style/asset/locale changes. Retain inherited source/notices.
This changes owned adapters only; no stock Odoo source or public DTO change.
