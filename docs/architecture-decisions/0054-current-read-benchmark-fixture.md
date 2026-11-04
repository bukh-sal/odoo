# ADR0054: align the retained unmanaged read fixture to the qualified image

Date: 2026-11-04. Status: accepted test-fixture procedure; current benchmark
measurement remains unqualified. Extends ADR0045, work item G-01c3/spec24.1.

The existing10k fixture is a logical clone, explicitly not a product deployment.
It has a separate filtered database/config/filestore/app/proxy, shared original
PostgreSQL process/network, paused copied dispatch, revoked technical credentials
and no issuer mount. It deliberately has no scheduler or lifecycle executor.
Keep those boundaries and the existing10k dataset. Do not turn this fixture into
a second product deployment or modify the SDK to accommodate its legacy names,
combined volume and shared PostgreSQL topology.

Read-only observation found exactly one installed native-version difference:
mp_core19.0.0.1.20 to19.0.0.1.23. The selected current14de image and ordinary
independent core23 rollout/recovery are already qualified elsewhere. For read
measurement setup only, stop this fixture's two known containers, capture its
complete DB/volume checkpoint, and initialize the retained synthetic fixture's
core schema using the explicit trusted-operator maintenance entrypoint. Hardcode
the exact recorded disposable DB/image/volume/network, verify paused dispatch,
zero active technical credentials, stopped fixture and original-runtime guards
before execution. Preserve the old containers and checkpoint until verified.
No application startup migration or public approval bypass is introduced.

This is test-fixture initialization, like the original explicit SQL dataset seed;
it neither exercises nor replaces product lifecycle approval. Product upgrades
continue through the independent executor, with existing core23 evidence retained.
Do not report this procedure as new upgrade/recovery acceptance. No issuer,
executor, scheduler or live external endpoint is introduced in the copy.

Republish only this fixture's sanitized planning/client-release metadata using
the existing pure SDK projection and verified current inventory/catalog. Its
OS-side fixture policy has no external endpoints; copied external features stay
suspended and credentials revoked. These public metadata writes grant no approval
or external authority. Keep all17 business/authorization/job/event tables exact,
including the10k Note dataset and copied paused control state, apart from the
declared native registry/publication change. Fail closed on any extra change.

Replace only the fixture app/proxy with the already qualified immutable images,
retaining its resource limits, combined owned volume, networks, loopback port
and non-conflicting app hostname. Never give it the original runtime's `app`
alias or compose-project identity. Preserve the original site's17tables,
app/DB/worker configuration and worker process/publication. Reuse the original
800request/20independent-session warm native/gateway list/detail methodology,
server filtering/pagination and unmodified admission controls. Record actual
engine/background sharing and latency tails; no target relaxation or new image.

Any uncertain fixture alignment stops for DB/child/checkpoint reconciliation;
do not replay native work. Retire only exact successful obsolete helpers/old
fixture containers after diagnostics, leaving required recovery inputs and
unrelated resources intact. Current OPS03/UI/performance/G7 remain open until
their actual measurements and remaining checks pass.
