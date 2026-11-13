# ADR 0087: Reviewed continuation after an unstarted restored fence

Status: source implementation under qualification, 13 November 2026. Installed
continuation and final lifecycle acceptance remain pending.

PP05 exposed a real host-operator defect after a completed native uninstall.
Source and restored dispatch fences shared an operation, review and action, so
they selected the same retained Docker child name. The source fence completed;
Docker refused creation of the restored child. The fresh database, filestore
and current-authority overlay had already completed. Replaying restore would
be wrong, and the earlier precreation continuation cannot describe this state.

Give the restored fence a deterministic purpose/database-specific correlation
UUID derived from the real review UUID. This changes only child naming; the real
review, exact hash, scope, operation and authority continue to authorize it.
Retain both children and all original evidence. Never rename or remove a child
to bypass no-reentry.

Extend the private OS completed-checkpoint continuation window only for this
proved historical refusal. Require the exact seven completed journal steps,
pending restore verification, one uncompleted restored-fence activity, exact
daemon name/ID conflict, empty output and absent result. Match the retained
source child's immutable identity, command, ownership, read-only mounts, network,
stopped successful state and protected result/activity records. Its Docker log
driver is `none`; protected stdout/result and completion digests bind success,
not an unavailable daemon-log claim.

Independently reobserve stopped ingress/workers, no clients/live maintenance,
unchanged source history/checkpoint/configuration/current authority/effects,
untouched restored dispatch, exact restored metadata/release, private credential
overlay, every filestore byte and canonical database digest. Plain dump hashing
streams under a 128MiB/60s bound, excluding only pg_dump comments/random psql
guard lines. Dump contents/stderr are not printed or retained. The independent
metadata observer's 16MiB limit stays unchanged.

A new expiring review binds those observations and current host source. Under
new real deployment/site locks, record a typed resolution of the unstarted
activity and adoption of the original pending verification. Preserve the old
intent, decision, failure, completed source operation and effect proof exactly.
New completion binds the adoption digest. Resume also validates the resolution
and reviewed source/history. Unknown partial states or drift still fail closed.

Continue only shared restore verification, distinct target fence, configuration
publication and guarded worker startup. Do not create/load the database, extract
filestore, reapply authority or replay the original uninstall. Finish closed;
require a separate current-state resume review. Record original restore failure
and measured continuation separately, never as a successful one-pass restore.

This deliberately expands one private operator recovery window. It adds no
public wire schema, browser approval power, application callback or universal
partial-operation reconciliation. Existing unresolved-failure/precreation flows
remain protected. Host repair bytes are separately reviewed; retained images
keep their original source identity. No runtime hash guard may be relaxed or
old image relabelled. Packaging changed host SDK bytes requires a future new
immutable candidate identity/build.
