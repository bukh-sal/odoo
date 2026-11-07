# ADR 0065. Measure capacity before automatic sizing

Status: BX-04 selected qualification envelope; implementation in progress.

Keep the reviewed single-host fleet and PostgreSQL queue. Add read-only,
release-pinned observations and capacity advice first. Advice cannot resize,
approve a profile, reopen dispatch or change workspace concurrency. Existing
operator profile review/apply remains the only resizing path. Missing, stale,
truncated or unhealthy observations produce hold reasons. A missing web latency
measurement is unknown headroom, never an implicit healthy signal.

Measure original eligibility separately from retry eligibility, future, expired,
held, unknown and obsolete work. Bound live-table observation at 100,000 jobs,
group output at 1,024 groups and recent worker logs at 2,000 lines per lane.
Use statement and lock timeouts. Export no input, token or job result. Aggregate
by pool, versioned handler and workspace so one hot workspace cannot appear to
benefit from extra lanes. Observe arrival and completion rates separately; a
recent preload burst is not automatically a sustained arrival forecast.

Worker timing includes a conservative preparation/claim/commit upper bound plus
the compute/apply attempt duration. Existing compute/apply duration stays
available. Retained log samples include versioned handler, timestamp, lane and
generation; pair attempts by job and generation. Incomplete attempts are not
completion samples. Do not combine samples from different releases or resource
profiles. These bounded samples are operational estimates, not durable billing
or an assertion that all historical attempts were observed.

For a handler, estimate work using the greater of its explicitly configured
default and recent p95 worker duration. Report sample count and fallback use.
Estimate ready and running worker-seconds plus explicitly forecast arrivals over
the drain window. Running work uses a full estimate conservatively. A target
includes measured startup reserve and is capped by approved pool bounds, the
eight-role site limit, available workspace slots and database connection budget.
Report an unattainable target instead of suggesting idle lanes. Count-based
advice remains a comparison policy. Keep urgent lanes warm. Never recommend
scale-to-zero in this qualification.

Before any test, freeze this local qualification envelope (not production sizing):

| Check | Workload and fixed target |
| --- | --- |
| BX04-01 | Repeat BG-04's 1,000 tasks, 150 reminders and 40 native reports through stock Odoo HTTP. One urgent/two bulk, three web workers and four PostgreSQL CPUs. Urgent start p95 ≤3 s; oldest ready urgent ≤10 s; bulk drains ≤120 s. Native list/detail p95 <500 ms and ≤1.25× paired idle. |
| BX04-02 | Sustain the Aurora-style native report workload for ≥180 s: one hot workspace, then 70 workspaces. Start at 0.4 bulk jobs/s, with the original reminder distribution over the same observation window. Variable reference CPU costs cover approximately 0.1–2 s on this host; record actual worker timings. No lost/duplicate native effects, no authority leak, zero expired useful work at this admitted rate, queue returns to baseline ≤120 s after arrivals stop. |
| BX04-03 | Compare fixed two-bulk, count advice and estimated-work advice against the same deterministic arrival/runtime trace. Record predicted versus actual drain, worker-seconds, deadline misses and queue wait. Vary hot versus distributed work and recurring bursts. Predictions must state slot/connection constraints. A fast burst with a useful start window shorter than measured startup must warn; it cannot claim reactive capacity fixes it. |
| BX04-04 | Process loss with queued work, 70-workspace fairness, a controlled database CPU/connection pressure interval and stale/missing measurements. Recovery must preserve claim generations and scope; pressure/staleness must hold growth. Above admitted capacity, record misses and an unreachable target rather than weakening the targets. |
| BX04-05 | Native headroom while admitted load runs: connections ≤70% of configured maximum, no sustained database blocking >2 s, PostgreSQL CPU ≤85% of its allocation over 10 s, no new listen overflows. Saturation fault intervals are separately labeled. Retire disposable realms/candidates. |

These are chosen development qualification inputs based on the already verified
Aurora-style workload. They are not inferred production arrival rates. Change
them only as a new recorded experiment; preserve failed attempts and reasons.

Automatic bulk sizing is conditional. Enable it only if controlled profile
changes improve useful-job latency or worker use over the fixed baseline while
all web/headroom targets hold. Then qualify sustained signals, capped growth,
slow scale-down with active attempts, stale telemetry, dispatch closure, release
exclusion and rollback. If no useful benefit is observed, keep manual profiles
plus advice and record that decision with measurements. Multi-host orchestration,
a broker, extra pools and higher per-workspace concurrency likewise require a
measured gap; do not add them merely to complete a feature checklist.
