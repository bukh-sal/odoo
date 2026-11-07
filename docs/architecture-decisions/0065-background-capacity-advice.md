# ADR 0065. Measure capacity before automatic sizing

Status: BX-04 qualified; manual sizing and read-only advice retained.

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
credits already warm lanes for the whole window; only additional lanes lose
the measured startup reserve. Predict zero work time for an empty queue, and
report fast bursts needing more warm capacity separately from the drain target.
The target is capped by approved pool bounds, the
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

The controlled burst comparison fixes72 bulk jobs across70 workspaces, all
eligible together:18 native ten-row reports and54 CPU samples cycling250k,
1m and5m iterations. Keep the same150 reminders and paired stock Odoo reads.
Measure at least60s, retain bulk start p95≤60s and drain≤120s, and verify at
least64 simultaneously ready bulk workspaces. Compare two warm bulk lanes
with the count recommendation (one job estimated at2s) and per-handler work
advice (report default2s, CPU default0.5s plus observed p95). Reuse an actual
run if two policies select the same count. Record worker-lane seconds from
eligibility to bulk drain, plus lane time across the full measurement window.
Do not treat faster drain alone as useful-job benefit when all fixed service
targets already hold; compare deadline misses and resource use too.

Fairness also needs an adversarial service-order check:two workspaces each
queue30 equal-eligibility CPU samples while68 peers queue one each. With two
bulk lanes, require the first peer within four hot claims, and all68 peers to
start before either hot backlog consumes more than four claims. Per-workspace
concurrency alone is insufficient evidence for this condition. Preserve the
unmodified scheduler's result before changing its selection policy.

Automatic bulk sizing is conditional. Enable it only if controlled profile
changes improve useful-job latency or worker use over the fixed baseline while
all web/headroom targets hold. Then qualify sustained signals, capped growth,
slow scale-down with active attempts, stale telemetry, dispatch closure, release
exclusion and rollback. If no useful benefit is observed, keep manual profiles
plus advice and record that decision with measurements. Multi-host orchestration,
a broker, extra pools and higher per-workspace concurrency likewise require a
measured gap; do not add them merely to complete a feature checklist.

## Measured decision

Retain PostgreSQL, the urgent/bulk pools and independently reviewed manual
profiles with read-only advice. No automatic resizing controller is selected.
This decision concerns the admitted development workload, not all future apps.

Core44's identical72-job/70-workspace burst plus150 reminders passed every
fixed service/headroom target with two and three prewarmed bulk lanes. Fixed
and estimated-work advice selected two; count advice selected three. Two lanes
drained in24.631s and used49.262 lane-seconds, versus17.624s and52.873 with three.
Full-window use was120.429 versus180.385 lane-seconds. Both completed all222
useful jobs without expiry. The faster three-lane drain did not prevent a miss
or add useful completions under the fixed targets. It used more lane time.
[Corrected comparison](../evidence/post-r1/background-execution/bx-04-core44-burst-comparison.json).

The separate cold-only burst had ten seconds of validity. Reviewed growth took
26.407s; all20 jobs expired with zero attempts. Native advice warned that a
reactive start would miss the useful window. Keep urgent capacity warm and
provision predictable short bursts ahead of time; do not extend job deadlines
to make a sizing test pass.
[Cold growth](../evidence/post-r1/background-execution/bx-04-cold-start.json).

Recurring bursts, original paired load, sustained hot/distributed workloads,
child loss and isolated advisory-backend loss have distinct recorded evidence.
Connection pressure at50/64 connections held advice with null recommendations;
genuinely aged and missing health also held. Advice did not mutate the fleet.
[Pressure](../evidence/post-r1/background-execution/bx-04-pressure-stale.json) ·
[Recurrence](../evidence/post-r1/background-execution/bx-04-recurring-bursts.json).

No measured gap justifies a broker, more pools, higher workspace concurrency or
multi-host execution for this envelope. Fairness and isolated slot loss did
expose real defects; core44 fixes those while retaining the queue and authority
contracts. Those fixes were required, independent of the sizing decision.

Reopen automatic sizing when an app provides a different admitted arrival/burst
trace, service target or idle-cost requirement and a controlled policy change
improves useful results or resource use over its fixed baseline. Then the
controller's stale-signal, active downscale, release exclusion and rollback
drills become required. A dynamic one-lane baseline has not been tested here;
these measurements do not rule out savings for a different workload.

Capacity estimates are not global host reservations. Per-lane CPU/memory pins,
the site role cap and database connection budget constrain advice, but it does
not reserve memory/CPU against web, database or other deployments. Operators
must choose profile bounds within their deployment budget. Any future automatic
controller also needs authoritative host-wide resource accounting and a trusted
fresh headroom feed; the current CLI is not that controller or monitoring agent.
