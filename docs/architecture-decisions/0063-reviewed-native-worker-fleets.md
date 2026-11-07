# ADR 0063. Reviewed native worker fleets

Status: qualified for BX-02. The original BG reference
remains the measured capacity baseline. This change does not enable autoscaling.

The independent local operator owns a durable desired profile per deployment and
site. Review binds the exact database, site, image, inventory, published release
and full target digest, plus the observed containers and previous desired state.
Apply uses an expiring digest approval. It records an immutable intent before
atomically publishing the desired profile and then reconciling Docker. Retrying
an interrupted attempt resumes its current desired state. A superseded attempt
cannot overwrite a later profile. Private files use the existing protected
operator store. There is no application endpoint for infrastructure changes.

Use urgent and bulk roles on the same application image and private runtime
network. Each lane is one supervised process with its existing original-actor
authorization, short claim lease, release fence and workspace/pool slot. A profile
permits zero to eight lanes per pool, one to eight total, 250–2000 CPU millicores
and 256–2048 MiB per lane. The reviewed shutdown grace is 5–3605 seconds. Defaults
are one urgent lane, two bulk lanes, one CPU, 768 MiB and 45 seconds. These are
operator bounds, not a workload capacity promise. Review refuses requested
aggregate limits above the Docker host's memory or CPU capacity. The operator
must reserve capacity for PostgreSQL, web processes and other host workloads.

A count change retains lanes whose template still matches. A resource or pin
change replaces lanes from an earlier approved template. The reconciler refuses
unrecognized templates. Docker arguments and mounts are fixed by the operator;
plugins cannot choose them. Only one local command runs under the existing
deployment/site operation locks. The reconciler may report a partial result while
a lane starts. It never changes the database dispatch switch.

Readiness requires a matching container configuration and a fresh worker child
heartbeat with the reviewed database, site, inventory and release pins. The child
refreshes it only after checking dispatch or renewing a live claim. Paused,
draining, errored, dead or disconnected children are unavailable. Docker restart
policy provides process restart; it does not imply readiness. Status separately
reports desired, running, ready and explicitly drained counts for each pool.

Selected-lane drain persists the exclusion before disabling container restart
and sending SIGTERM. Reconciliation retains the exclusion. A new reviewed profile
clears selected exclusions. Full drain persists a paused profile. A lost stop
response can be reconciled without restarting the drained lane. The shutdown
grace permits bounded completion; a forced interruption relies on lease expiry,
claim generation and the existing effect policy. It cannot promise completion of
an attempt longer than its grace. Do not enable automated downscaling before
the active-attempt and forced-stop drills pass.

Native maintenance and fresh restore require the profile paused and every job
lane stopped, under the same locks as resizing. Legacy running lanes are refused
too. After upgrade or separately authorized restore/resume, review a new profile
against the new target. An old profile cannot start lanes on changed pins.
Legacy start/drain remains available before profile adoption; drain legacy lanes
before adopting one. Thereafter use reviewed profiles for all starts and resizing.

Qualification must cover partial starts, interrupted intent publication, stale
review and wrong-pin refusal, connection loss, selected and active drain, forced
interruption with stale-claim denial, a resize racing maintenance, resource usage
and new-release profile adoption. See the
[follow-up checklist](../implementation-status.md#post-r1-work) and
[BX-02 plan](../../planning/background_execution.md#implementation-gates-and-acceptance).
