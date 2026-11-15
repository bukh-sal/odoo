# ADR0094: Shared record presentation, app-owned rich contributions

Date:15November2026. Status: accepted for local implementation.

Informational records need coherent identity, cards, section navigation and
explicit Edit, while optional apps contribute useful current data. Existing
trusted native widgets, view inheritance and Workboard task panels demonstrate
this without a compulsory generic domain model.

Core will supply reusable RecordTabs/RecordSection presentation and an opt-in
native header arrangement. The owning native app defines its ordered rich
component seam and record semantics; optional providers reauthorize actual reads
and actions and clear stale content. Registry presence does not mean installed,
enabled, accessible or available. No finance logic or fixed app ID in core.

Frozen ui.slots kind=actions remains unchanged. A rich record section is not
silently admitted as that action protocol. A future portable rich-slot wire
contract would need its own explicit supported semantics, ADR/freeze and real
qualification; it is not a prerequisite for trusted native author composition.
This preserves the R1 trusted Python/same-origin frontend boundary and makes no
sandbox claim. Presentation never supplies write authority.

Native models, scoped ORM/service permissions, explicit CAS, immutable archives,
independent approval/checkpoint/recovery and source ownership remain authoritative.
Source and mounted proofs do not replace installed UI/current-authority/app
absence evidence. See ui-informational-record-composition-plan.md for the current
coherent implementation and delivery scope.
