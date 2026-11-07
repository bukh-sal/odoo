# Read-only background capacity advice

Read-only advice and its load/pressure/recurrence behavior have native evidence.
BX-04's recovery and retirement checks passed. The fixed
qualification targets and scoped manual-sizing decision are in
[ADR 0065](architecture-decisions/0065-background-capacity-advice.md).

Use the independent local operator with a current reviewed fleet. `jobs
capacity` exports a bounded queue snapshot, database connections/lock waits,
ready counts, release/resource pins and recent per-handler worker durations.
It reads only, taking the existing deployment/site locks while observing.
Export its JSON to a private file using the same `--store`,
`--deployment-config` and `--config` arguments as other `jobs` commands.
Then `jobs advise --observation <file> --policy <file>` reports estimates and
constraints. It never approves or applies a profile. Start or change lanes
through the existing independent `profile-review`/`profile-apply` commands.

For example, a qualification policy for one optional producer is:

```json
{
  "protocol": 1,
  "maximum_age_seconds": 30,
  "startup_seconds": 10,
  "drain_seconds": 60,
  "pools": {
    "urgent": {"minimum": 1, "maximum": 1, "start_target_seconds": 3},
    "bulk": {"minimum": 1, "maximum": 6, "start_target_seconds": 60}
  },
  "handlers": {
    "org.example.background:report:2": {
      "pool": "bulk", "default_seconds": 2, "arrival_per_second": 0
    }
  },
  "headroom": {
    "web_p95_ms": 500, "db_cpu_fraction": 0.85,
    "connection_fraction": 0.7, "lock_wait_seconds": 2
  }
}
```

Choose measured startup time and defaults for the actual deployment. Add every
handler with runnable demand; missing estimates hold advice. Arrival forecasts
are explicit inputs, distinct from observed recent arrivals. They are distributed
across observed workspaces for that handler, which is an approximation stated
by the report. An arrival forecast with no observed workspace holds advice.
Pool maxima plus producer count may not exceed eight. Urgent capacity receives
the shared spare connection budget first. Running work is conservatively charged
a full handler estimate, not discounted using unverified progress percentages.
Warm lanes contribute immediately; only newly requested lanes lose startup time.
The warm capacity required for the start target is a separate diagnostic from
the drain-window estimate. Cold capacity cannot repair an already late burst.

The queue snapshot does not know HTTP latency or PostgreSQL CPU headroom.
Attach a `health` object from a trusted deployment monitor or the qualification
harness, using the measurement's actual timestamp:

```json
{
  "observed_at": "2026-11-07T06:00:00+00:00",
  "web_p95_ms": 220,
  "db_cpu_fraction": 0.45,
  "lock_wait_seconds": 0
}
```

Missing, old, future-dated or saturated health yields `state: hold` and null
`advised_lanes`. Queue estimates and constraints remain visible for diagnosis.
CPU fraction is relative to the PostgreSQL container's allocation over the
measurement interval; the qualification uses ten seconds. Changing worker
image, target or per-lane resources invalidates old observations. Counts alone
do not turn this JSON into an approval or make it safe to run an autoscaler.

A hot workspace can execute only one job per pool. An estimate of five lanes
for two workspaces reports the slot constraint; the extra lanes cannot resolve
it. Bursts whose useful start window is shorter than startup need warm capacity
or admission changes. The report warns about late reactive starts and expiry.
Policy defaults, forecasts and p95 estimates are capacity estimates, not execution
or deadline guarantees. No native job authority, credential or effect semantics
are changed by advice.

The measured envelope retains reviewed manual profiles:two warm bulk lanes met
all fixed targets with less lane use than the count-based three-lane choice.
No automatic controller, broker or additional pool is enabled. Short-validity
bursts need warm capacity; measured cold growth exceeded a ten-second window.
Reopen the decision with an actual app trace and a useful benefit over its fixed
baseline, then qualify the controller's downscale/release/rollback behavior.

This report does not reserve host memory/CPU against other deployments or the
web/database roles. Set approved pool maxima within that budget. Host-wide
resource accounting and a trusted telemetry feed are prerequisites for a future
automatic controller. Current advice is bounded operational estimation.
