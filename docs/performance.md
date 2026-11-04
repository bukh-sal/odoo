# R1 performance qualification

The current read target passed on the retained 10,000-note fixture with image14de,
PostgreSQLd81 and proxydece. [Actual qualification](evidence/G7/20261104-performance-current-01/read-qualification.json)
binds the source, resources, raw samples, dataset and preservation checks.
This completes the read half of the performance slice, not full G7.

| Ordinary authenticated path | Samples | Median ms | p95 ms | Max ms |
| --- | --- | --- | --- | --- |
| Native Odoo list,80rows |200|153.311|303.779|1089.874|
| Native Odoo detail,9600byte body |200|57.795|107.879|1037.560|
| Gateway list,25rows |200|125.764|360.509|1092.501|
| Gateway detail,9600byte body |200|91.218|162.812|1085.332|

All 800 requests succeeded. Each case used 20 independently authenticated sessions,
three warmups and ten batches released through a barrier, with1.15seconds
between completed batches. Normal workspace/release/binding/CSRF checks and
proxy admission remained enabled. This measures concurrency bursts; it is not
a sustained 20 requests/second throughput claim. All 37 requests above 500 ms remain
in the raw evidence; the specified p95 target is not a uniform latency bound.

The database has 10,006 Notes, including exactly 10,000 in workspace A and 9,976 retained
synthetic rows with the original deterministic body distribution. Server-side
filtering,80row native limits and disjoint25row gateway pages were verified.
The Note dataset, all17benchmark business/authorization/job/event tables,
paused copied dispatch and revoked technical credentials remained exact.
The original site's17tables and protected PostgreSQL/worker identity also stayed
exact. No image, volume, network, database or reseeded dataset was added.

Docker reported16CPUs and8,290,824,192bytes of memory. The benchmark app retained
2CPU/1536MiB/two workers, and the shared PostgreSQL process1CPU/512MiB. The
proxy retained 0.5 CPU/128 MiB. Other containers and the physical host/network are
shared; [actual resource metadata](evidence/G7/20261104-performance-current-01/resources.json)
does not imply dedicated4CPU/8GiB hardware or arbitrary deployment guarantees.

The earlier31-image benchmark's gateway-list p95 was 254.463 ms versus 360.509 ms
now; medians were 127.169 ms versus 125.764 ms. Both datasets and the methodology
are retained, but dependencies/background conditions differ, so this is not a
controlled causal regression or improvement claim. All four current p95values
are below 500 ms. The warm upstream session control was 7.724 ms p95; its coarse,
different-actor/environment R0reference31ms is contextual. The remaining
performance review must retain those comparison limits.

[ADR0054](architecture-decisions/0054-current-read-benchmark-fixture.md) explains
the explicitly unmanaged fixture alignment. Product lifecycle approval was
already qualified separately and was not replaced by this test setup. The copy
has no issuer, executor, scheduler or live external endpoint. Private database,
configuration/filestore checkpoints and preservation snapshots are recovery/test
inputs; they are not public diagnostics. Three exact successful obsolete
containers were retired after checkpoint/inspection/native diagnostic capture.

The fixture is retained at port18089. Its once-only setup/qualification scripts
and `.local/g7-performance-current-01`/`.local/g7-performance-10k-01` records
must be inspected before any new measurement. Do not rerun setup, reseed,
reset its database or replay its core initialization. New measurements need an
explicit new output record and confirmed current target identity.

The current managed release reference also passed the shell and disposal checks
in [the actual browser qualification](evidence/G7/20261104-ui-qualification-01/performance-qualification.json).
Edge156 used production minified assets and one protected owned profile, with
no personal browser or additional Docker assets. Login to interactive native
Notes plus the actual Odoo command palette took990.425ms with cold browser
cache and586.731/887.474/742.008ms with warm cache. The server was warm.

After five warmup cycles,100actual Canvas→Settings transitions left every
Canvas root disposed. Post-GC heap grew95,568bytes from7,283,236to7,378,804;
documents33/nodes2630/listeners151 stayed constant. The full six-point curve
and predeclared limits are retained. This establishes no unbounded growth
observed in this finite run. All17business/authority/job/event tables and all
four runtime process/image/mount/network identities remained exact. The owned
browser exited0 and no process using its profile remained. The profile stays
private for subsequent justified tests. Screenshots and diagnostics were checked
against133known credential values with no findings.

The remaining source-bound observability review passed in
[the current review](evidence/G7/20261104-observability-01/source-bound-review.json).
Twenty-one actual live app files match current source, including ten complete
files unchanged from qualified G6. The upstream session control is7.724ms p95
against the coarse R0reference31ms; different conditions preclude a speedup
claim. R0 had no matched Notes/custom-shell dataset. The additional authority and
release checks are an explicit cost covered by the passing current read targets.

The review found and corrected a private operator diagnostic gap:
[ADR0056](architecture-decisions/0056-independent-executor-observation.md) adds
a5second observation heartbeat and20second stale warning to independent CLI
apply/restore/resume and show. The actual forced-death test detected staleness
19.860seconds after kill; concurrent writers were refused.19affected tests
passed. This changes operator tools only; public HTTP DTOs, SDK and immutable
app/worker code remain unchanged. Final source-kit inclusion is still required.

Supported native child commands time out after300seconds, general Docker
commands after60seconds, and readiness has a90second deadline with bounded
probes. These bound observation/waits; killing a Docker client never proves its
child rolled back. Phase history and possible-effect fences remain authoritative.
Readiness includes expected inventory/release/registry and metadata verification,
separate from process liveness. Actual native failure/restore and optional worker
outage behavior retain their qualified proofs at the unchanged source boundaries.

Jobs default to a30second lease and120second deadline. A running compatible
runner sweeps on the next available claim iteration, normally at1second idle
polling. A stopped runner has no reaping-time guarantee; the reference UI uses
bounded observation and reports pending/unknown. No scheduler, OS scheduling or
trusted native code preemption guarantee is implied. Current request/write and
external result application recheck authority. Internal serializer snapshots
expire within20ms and invalidate on exit or mutation; they are not cross-operation
authorization caches.

Structured diagnostic equivalents are recorded in
[the read-only current sample](evidence/G7/20261104-observability-01/structured-diagnostics.json):

| §24.2 requirement | Diagnostic source |
| --- | --- |
| Request latency/error rate | Retained800request benchmark, proxy/Werkzeug status and duration; audit request IDs |
| Registry readiness/release | Guarded startup, expected inventory/release, independently verified native publication |
| Plugin health | Scoped manager health projection; qualified optional-worker outage UI/errors |
| Job depth/attempts/age | Current read-only aggregate sample and actor-authorized job state/progress |
| Outbox failures/lag | Pending count/oldest age and delivery state/attempt aggregates; qualified G6 failures |
| Deployment phase/duration | Independent UTC phase history, elapsed observation and stale warning |
| DB saturation | Current pg_stat_activity counts and max_connections, without query bodies |
| Worker CPU/memory | Actual four-container Docker resource samples |
| UI mount/release errors | Structured code/request ID alert and qualified release mismatch/disposal behavior |

The sample has one completed job and three pending outbox events; their actual
age remains visible. It is a point-in-time observation, not a new publication
test, metrics daemon or alert-delivery guarantee. No document bodies are logged.

The performance slice is qualified; required work remaining outside it:

- Browser/network, identity-cache and accessibility checks plus final G7 handoff.
- Final operator-tool source-kit refresh and release/privacy closure.
