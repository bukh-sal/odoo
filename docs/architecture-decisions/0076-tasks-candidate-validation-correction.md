# ADR0076. Preserve admitted candidate identities when correcting Tasks

Accepted8 November2026 during AT-03 qualification. The actual first image/package
installed through independent site-native approval and passed10 native workflow
checks plus20 managed reminders. A further rollback-isolated negative check found
that the default member relation hides inactive users, so the member constraint
accepted an inactive external user. A minimal reproduction proved that explicitly
including inactive relation rows detects it. Those results do not qualify AT-G/H
or a final release. Preserve their receipts and admitted archive bytes.

Fix validation using the complete relation under `active_test=False`; this does
not grant access to those users. Existing native owner/member/assignee rules and
the no-workspace reminder model remain authoritative. Issue application0.2.1 with
native version19.0.0.2.1; never replace admitted0.2.0 bytes. Move the bounded
missing-stage migration to the selected target version and declare explicit
0.1.0→0.2.1 and0.2.0→0.2.1 transitions. The supported legacy47 adoption remains
a separately reviewed closed operation, not an ordinary fresh install.

Source review also identified that closed job reconciliation still expects a
workspace binding for every row. Add native classification using the fixed native
definition, real installed target artifact, original human and current resource
authority. Only the already paused/restoring source release may be inspected;
normal dispatch/apply still require current release. Preserve native payload,
deduplication identity, actor, recipient input and timing; advance existing claim
and dispatch generations. Do not fabricate a binding or enable dispatch here.
Prove native positive/negative carry-forward and preserve workspace regressions.

Revision23 changes only the selected application version in the frozen contract
and records this compatible decision. Public v1 wire schemas and native authority
semantics remain unchanged. Requalify G2 and the affected runtime checks; previous
receipts keep their precise candidate scope. Final browser, populated update,
independent recovery and reproduction remain required. This decision grants no
implementation credit merely for changing source or documentation.
