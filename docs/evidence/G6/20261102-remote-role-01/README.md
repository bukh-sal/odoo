# Actual original-actor membership revocation

Current native18/88/BB1, installed NotesStats0.1.0 and metadataStats0.1.1,
canonical worker05/image1d/config3/publication5. Product source unchanged from
`79145cc2`. Both checks completed; do not replay their jobs or fixture changes.

Alice used the normal authenticated workspace member API to add Bob as an editor
in disposable workspace C. Bob enqueued an actual revision-bound analysis job.
Revoking his membership before the ordinary independent worker CLI claimed it
produced one terminal FORBIDDEN failure with no result. Restoring his membership
allowed him to read that saved failure through the normal status service.

For a second Bob job, the actual independently selected inventoried job process
ran its normal startup validation, registry, original-actor preparation, detached
bridge and signed request to the real worker. A test-only Python tracing callback
paused the unchanged `run_once` after `jobs.compute` returned and before opening
the finalization cursor. The callback recorded only job ID and a computed-value
digest. It replaced no function, authority reader, transport or result, and
changed no image/source file. This is explicit test instrumentation, not an
unmodified ordinary CLI launch for the second case.

While the real result waited, Alice revoked Bob through the normal member API.
His status request immediately returned403. Releasing the bounded barrier let
the actual `finish_one` recheck current authority and commit one dead-letter
FORBIDDEN outcome, no stale result. Restoring editor access proved saved status
remained readable, then normal removal returned Bob to no active C membership.

The first harness incorrectly expected a viewer to be unable to read their own
status. Its200 response was permitted by this read-only service. Inspection
confirmed the assumption was wrong; no runner had started. A fresh read-only
continuation confirmed the same single pending job/unchanged worker, then removed
the actual membership rather than denying permissible viewer reads. No enqueue
was repeated and no product contract/source was changed.

All original22 jobs and all unrelated rows of the17 baseline tables remained
exact. Explicit footprint:2 new one-attempt dead-letter jobs,1 new revoked test
membership retained as history, C policy generation+7. The independent worker
identity/image/start/key/network/publication remained exact. The instrumented
runner auto-removed; no persistent Docker assets were added.

This proves real current original-actor authority at dispatch and after remote
I/O. It does not independently qualify every binding/grant/feature/credential/
publication transition, uncertain external effect/recovery, changed-image case,
or browser rendering. Acceptance remains93/99, roughly89% weighted progress.
