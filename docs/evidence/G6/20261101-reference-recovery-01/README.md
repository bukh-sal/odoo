# Reference-aware recovery source checkpoint

F-01d prerequisite, spec §§10.5, 13, 14.6, 25; ADR0034.

`qualification.json` records 57 passing host-source checks, including 15 new
reference epoch/current-authority/resume checks. Docker, database restore,
checkpoint and publication effects are substituted. This does not qualify a
committed external metadata operation, external recovery or SVC acceptance.

The existing recovery/private-review/native-auth/unchanged-base suites also pass:
`python -X utf8 -m unittest discover -s tests -p '*recovery*.py'` ran 23 tests in
172.269s (discovery began before the new reference test file existed). These use
real temporary OS stores/locks/reviews and filesystem extraction where their
fixtures specify it, with no Docker assets or live database mutations. The new
reference suite is counted separately in the 57-test report. Total: 80 checks.
The frozen 94 files/eight contract rows remain unchanged and pass the checker.

Recovery selects only exact checkpoint or independently approved target metadata
for read-only failed-source inspection. A restored database must have the exact
checkpoint-derived new epoch and generated fresh database name. The reference
policy binds actual metadata registrations and the current independently owned
publication; endpoint approvals and key material are never restored from the
database checkpoint. A fresh resume review can bind a changed publication only
when all queue/control/registration/image fields remain exact. A later change
invalidates that review before the durable traffic fence/queue enable boundary.

Checkpoint manifests now retain the private reference policy needed to compare
an untouched restored target during the already-bounded pre-fence continuation.
Native defaults remain conservative. Metadata operations select their adapter
on recovery CLI construction even when first registration never published the
new target configuration. Unchanged recovery retains its no-mutation guards and
selects the reference profile only from the controlled published release.

Limits: the known reference uses the same immutable worker image. A different
worker-image transition and installed continuation/unchanged paths still need
actual qualification. Missing trust or unknown effects fail closed. No new
image was built; none of this code is installed in the current runtime.

Next: preserve controlled external metadata pins during native staging/core
coverage, close the connector final-apply authority gap and queued native-feature
path, then build a coherent core/SDK image and qualify the real reviewed metadata
lifecycle/recovery. Do not replace those runtime checks with more source mocks.
