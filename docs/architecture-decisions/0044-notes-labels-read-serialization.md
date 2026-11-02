# ADR0044: reuse the qualified finite window for Notes/Labels reads

Date: 2026-11-02. Status: installed correction and small-data HTTP discriminator qualified; required10k target pending. G-01c2b/c, §24.1; requires qualified ADR0043/core20.

Core20 alone reduces the warm native24-row list from519 to123SQL queries, but gateway DTO serialization still uses816queries. The gateway constructs DTOs directly, outside native `read`, and Labels repeats optional-feature policy queries per field/row. This is the remaining measured amplification, not a reason for a new cache subsystem or frontend rewrite.

Notes0.2.8 explicitly wraps each finite list/get/v2 read result recordset in the qualified native read window and uses `_mp_read_scope` in its DTO. Calls outside the window still use the full guard; mutations do not opt into a serializer window. Labels0.2.4 opts into the bool-only window policy helper for optional-feature read availability and read field access only. Every write permission/availability check remains fresh, including writes called from inside a read window. Existing ORM/SQL dirty-state invalidation and20ms expiry apply to policy booleans as well as scope.

Both plugins require platform>=0.1.20. Labels requires Notes>=0.2.8. Preserve prior archives and all97frozen contracts, DTO schemas/field semantics, native views, CAS, events, Canvas, worker and business schema. Use a separate ordinary curated immutable plugin upgrade, not a core upgrade or direct database metadata edit.

Required proof: candidate actual native DTO list/get/v1/v2 and optional-feature read behavior, policy memoization/expiry/mutating SQL/dirty ORM invalidation, current viewer/technical and write-availability denials inside windows, cross-workspace/actor/mixed records, no after-exit reuse. Then actual installed regression/HTTP/native list-form contracts and populated preservation. Measure real HTTP before the isolated10k/20concurrent qualification. No claim that a24-row SQL discriminator passes §24.1.

Discriminator: first compiler3302 and actual installed Labels3 both preserve stale Labels read availability after pending ORM installation suspension; actual cached field read reproduces the gap onlivecore20. Feature suspension already denies. Preserve both rollback-only probes in notes8-labels4-read-01. The correction flushes only queried installation/feature policy fields before availability SQL; no business-data flush or policy-cache bypass. ID03 is temporarily invalidated until actual immutable plugin correction/regressions pass.

Installed qualification: `../evidence/G7/20261102-notes8-labels4-read-01/qualification.json`. Ordinary reviewed five-scope operation2abd82cd completed29/132;63native/31HTTP/Canvas and strict populated/schema/files/worker preservation passed. ID03 requalified. Warm candidate native24list45SQL/gateway29 vs prior519/816.21temporary containers/3unused images retired. Full HTTP/10k target/G7 remain.

Actual HTTP diagnostic: `../evidence/G7/20261102-read-http-discriminator-01/comparison.json`. Same recorded resource caps/proxy/authorization,20independent concurrent sessions/40samples per case,30total24workspaceNotes: native list/detail p95178/120ms, gateway187/156ms,0errors. Maximum~1.1s remains recorded. All17tables/worker exact. This confirms the bounded correction, without passing the required10k benchmark or adding gate points.
