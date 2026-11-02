# ADR 0037: observe independently approved endpoints before re-registration

Date: 2026-11-02. Parent F-01d, specification14.6, ADR0034/0036.

Actual installed core15 HTTP re-registration with a deliberately stopped worker
passed independent planning/review/approval but failed in dispatch observation:
the removed-tombstone guard required all endpoint approvals to remain revoked.
Registration requires a separately approved enabled endpoint first. This made
the required ordering impossible after unregister, although first registration
already permits an approved endpoint with no installation row. Failure occurred
before dispatch fencing/checkpoint/metadata mutation; ingress stayed closed.
Evidence: G6/20261102-manager-reregister-01/failed-apply-audit.json.

Permit a removed reference installation to coexist with one independently
approved enabled endpoint only when the feature remains suspended, no approved
grants or active provider/consumer bindings remain, and the endpoint's exact
site/scope/image matches both the retained manifest and independently selected
reference runtime. Preserve absence/revoked endpoint recovery behavior. Reject
enabled features, foreign scope/image, suspended or duplicate endpoints, active
bindings and grants. Existing global credential/unknown-effect refusals remain.
No generic external/degraded override, runtime orchestration or implicit feature
activation is introduced. Current gateway/native authority still rejects removed
metadata; an OS endpoint approval alone never creates host dispatch authority.

This corrects the private reference observer, not a public DTO or approval rule.
No schema, golden, token or G2 frozen file changes. Regression checks must invoke
the real reference_policy with controlled independent IO and include the actual
captured profile. Use fresh exact reviewed unchanged-release recovery for the
failed pre-mutation operation, retaining original data and current publication.
Do not replay that failed operation. A corrective immutable core/SDK16 rollout
must precede a new metadata apply because its source preflight compares exact
component hashes; no application image/source hot patch is allowed.

Source qualification and restored ingress alone do not pass re-registration,
external recovery, SVC04/05 or G6. Return to the same stopped-worker registration
case after immutable rollout, then minimal connector/remote/recovery/image
transition qualification. Browser rendering remains separately pending.
