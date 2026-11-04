# ADR0051: native uninstall with the existing durable dispatch fence

Date: 2026-11-04 (Asia/Riyadh). Status: accepted design; implementation and installed qualification pending.

The current core22 qualification site has native plugins, one independently operated
reference worker, and populated durable history. A read-only Labels impact request
fails because its service-binding validation omits the published external metadata
package. The planner and fixed uninstall child also explicitly reject dispatch
tables. Earlier native-only G5 uninstall evidence does not qualify this integrated
R1 profile. Evidence: `../evidence/G7/20261104-native-uninstall-dispatch-01/read-only-refusal.json`.

Reuse the existing independent catalog, NativeExecutor, dispatch maintenance,
coordinated checkpoint, ReferenceRecoveryDispatch and separately reviewed resume.
Do not add a second installer, a public approval override, queue deletion, or remote
undo. Independently select external descriptors from the exact published release;
read their manifests as data for binding validation, never as native source.
Native uninstall keeps its exact actual dependency closure and upstream operation.
An external required consumer of a removed native provider must be unregistered
first; it cannot be silently cascaded by a native uninstall.

Contract major1 revision18 adds `present_requires_fence` to lifecycle-impact dispatch
state, only for the existing exact base or event dispatch schema. This is an
observational prerequisite, not authorization. Unknown/partial schemas remain
unsupported. Existing payloads remain valid; old strict readers may reject the new
enum, so operator and application must be upgraded together under the existing
immutable image/source checks and client release fence. No forward-reader claim.
Keep all eight contract ownership rows and the original G1 evidence. Requalify
fixtures and affected consumers before freezing revision18; never only bless hashes.

Pass the private coordinated checkpoint's exact closed dispatch snapshot and typed
scope/reference policy into the fixed child. Re-observe the recognized scope,
schema, control generation, queue/history digests, credentials and uncertainty
before importing Odoo. Require the same snapshot after the genuine native commit,
before metadata reconciliation. Any mismatch is a post-mutation failure requiring
the existing fresh-database restore, never a replay or a same-database reset.
Normal reconciliation may subsequently advance generations under existing rules.

Required qualification: old/no-dispatch payloads; complete base/event schemas;
partial/unknown schema, stale snapshot, open control, credential, uncertain-effect,
missing package and required external-consumer refusals; actual current Labels
impact/uninstall with preserved durable history; controlled post-native-commit
failure, fresh named database restore and separate exact resume review. LIFE03/04
are pending current integrated requalification; unaffected source-removal guards
and native-only historical proofs remain retained. OPS02/MIG09 remain pending.
Use one core23 maintenance image after tests and contract freeze; preserve existing
application/worker/data until the ordinary independently reviewed rollout.

This required R1 lifecycle correction adds no dependency, worker implementation,
Canvas feature or frontend rewrite. Standard record screens remain native Odoo.
