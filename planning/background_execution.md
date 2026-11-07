# Background execution for job-heavy apps

This post-R1 work is based on the qualified `stock-r1` platform and Aurora `bedrock-2.2` at `e48e04ed4cf155a83e66e08dfb33a669ebb5c228`. It does not reopen the original R1 qualification. The comparison uses checked-in code and retained evidence.

Keep the platform's PostgreSQL queue and guarded execution. Use Aurora's enqueue experience, named pools and operational visibility as the model for what app developers and operators should see.

| Area | Platform today | Aurora `bedrock-2.2` |
| --- | --- | --- |
| App API | The private `JobDefinition` and bound enqueue path register versioned, schema-checked prepare, compute and apply functions. Status is scoped. The Notes examples expose specific operations. | `BackgroundWorker/enqueue.py` accepts a Python callable or dotted path, JSON arguments, a pool, a future time, an attempt limit and a retry interval. It returns a task ID. |
| Scheduling and routing | The queue stores when work is available and when it expires. The current enqueue primitive makes new work immediately eligible. The native loop polls with a bounded interval and claims registered handlers. | `execute_after` supports future work. The DB backend claims due rows, and the Redis worker promotes scheduled items. Workers are assigned to pools such as `general` and `logs`. |
| Retry and cancellation | The queue has retry, lease expiry, deadlines, progress, cancellation and dead-letter primitives. The current native runner classifies detached computation errors as nonretryable. Its reference behavior is narrower than a supported API for all of these controls. | Worker exceptions drive retries and dead letters. Django admin can inspect tasks and retry failed DB tasks. Its cancel action marks DB rows completed and leaves a running callable executing. Redis mirror rows are read-only. |
| Authority and recovery | Dispatch reconstructs the original actor and rechecks current authority and resource state. Database effects commit behind the current claim in the same transaction as completion. Uncertain external outcomes can be recorded for reconciliation. G6 proved these boundaries for the reference cases. | The worker imports and calls the queued function. Authorization, deduplication and side effect handling depend on that function. Redis pops before separately recording the claim. A crash between those commands can lose the task. A visibility timeout can also reclaim work while the original process is still executing. |
| Operation | A native polling loop exists. The selected kit uses the operator's `run-job-once` for the reference workflow. The separate document statistics service is a scoped computation provider. | Separate worker processes, a launcher for multiple pools, and container restart policies are wired in. Workers finish the current task on graceful shutdown. |

Platform references are the [durable queue](../packages/platform_sdk/modular_platform/durable.py), [registered dispatch](../platform_addons/mp_core/job_dispatch.py), [native runner](../packages/platform_sdk/modular_platform/job_runner.py), [stock kit reference run](../release/connect_worker.py), and [G6 evidence](../docs/evidence/G6/20261102-headless-ui-01/gate-G6.json). Aurora references are `BackgroundWorker/enqueue.py`, `BackgroundWorker/backends/{db_backend,redis_backend}.py`, `BackgroundWorker/admin.py`, `BackgroundWorker/management/commands/run_worker.py`, and `compose.dokploy.yml` at the pinned commit above.

## Sequence and exit checks

| Gate | Work and prerequisite | Exit evidence |
| --- | --- | --- |
| BG-01 | Pick the workload before freezing the contract. Start with an Aurora-style task reminder and a concurrent synthetic bulk report or import. Record expected rates, bursts, payload sizes, maximum useful delay and runtime, and targets for the oldest ready job and web latency. | A workload and failure matrix distinguish database effects, external effects and ambiguous outcomes. Capacity targets reflect an app's expected load. |
| BG-02 | After BG-01, freeze a trusted plugin contract over the existing queue. Use registered versioned handlers, a compact validated payload, an idempotency key, and a server-derived site, workspace and actor. Support `run_at`, status, progress and cancellation. Separate when a job becomes eligible from its expiry and its per-attempt runtime limit. Specify enqueue transaction behavior, retryable error classes, bounded backoff, and compatibility for queued jobs after an upgrade. Give unattended jobs an explicitly scoped service identity where the workflow requires one. | Rollback leaves no runnable job. Duplicate submission has one intended effect. A delayed job rechecks current rights and record state. Cancellation, expiry and incompatible handlers produce observable outcomes. |
| BG-03 | After BG-02, deploy continuously supervised workers using the existing release and dispatch guards. Start with an urgent pool and a bulk pool, with independent concurrency and per-workspace limits. Qualify worker restart, graceful drain, bounded execution and lease renewal for long jobs. Expose scoped status and operator actions for failed work and unknown outcomes. Measure queue depth, oldest eligible age, time to start, duration, retries, expired leases and failures by pool. | Kill a worker after claim and after effect start. Prove that a replacement takes eligible work, an old claim cannot commit a database effect, and ambiguous external work goes to reconciliation. Restart and upgrade while the queue is populated. |
| BG-04 | After BG-03, run the reminder and bulk workload together on the reference deployment. Measure urgent start delay and web latency alongside throughput, queue growth, PostgreSQL usage and recovery time. | The urgent and web targets hold under the recorded load. Backlog drains after a burst or worker restart. Add recurring schedules, additional pools, or a broker when a workload and measurements justify them. |

The first reminder should re-read the task, due date, completion state and current recipient at dispatch, as Aurora already does. Give each reminder occurrence a stable effect key and create the notification record and outbox entry in one transaction. A changed due date makes the old occurrence obsolete. A push adapter should use provider idempotency where available and report uncertain delivery for reconciliation where a safe replay is unavailable. This exercises scheduling, authorization, cancellation and delivery without requiring an Aurora data migration. The synthetic bulk job tests contention that a reminder alone cannot reveal. See Aurora `Tasks/notifications.py` and platform [spec §§14.2–14.3 and §24](modular_platform_spec.md).

## BG-01 reference profile

Use two workspaces on a disposable stock WebClient deployment with 500 synthetic tasks each. The workload is an engineering reference, not a claim about Aurora's traffic. [The deterministic generator](../tests/background_workload.py) specifies the exact input mix. Preload two reminders per second for 60 seconds and a burst of 30 at second 20; a task reminder has 60 seconds of useful life after eligibility. The concurrent bulk pool receives 40 reports at second zero, each aggregating 500 scoped rows in batches and computing a deterministic checksum. Each bulk attempt has a 20-second runtime budget and the report has a 180-second useful window. Report parameters reference IDs and a bounded range; they do not contain the dataset. Start with one urgent slot and two bulk slots, with at most one bulk job running per workspace.

| Check | Pass condition |
| --- | --- |
| BG-01a — reproducible input | Generator emits 1,000 tasks, 150 distinct reminder occurrences and 40 bulk requests; two workspaces and bounded payloads; matching digests for repeat generation. |
| BG-02a — transaction and deduplication | Source rollback removes the queued write; concurrent equivalent requests resolve to one job; a changed payload or schedule under the same key is refused. |
| BG-02b — lifecycle and scope | No early claim; expiry and cancellation are observable; fresh authority and record state are rechecked. Due date, assignment, or completion changes suppress obsolete reminders; current occurrence emits one notification and one outbox event. Foreign scope cannot inspect or cancel. |
| BG-03a — execution | Observe per-workspace/pool limits, progress, heartbeat, retry, runtime timeout, restart, and graceful drain. Kill a worker after claim; verify reclaim and stale generation denial with no duplicate database effect. |
| BG-03b — effect recovery | Before send, retry safely. After send with no acknowledgment, a reconcile-mode fake sink must retain one observed effect and the queue must remain unknown until separately resolved. No live provider. |
| BG-03c — release | Upgrade a populated queue using the independent lifecycle controls. Delayed compatible jobs preserve timing and original scope; incompatible jobs hold; an obsolete worker cannot commit. Restore and resume use separate authority. |
| BG-04a — mixed load | Under the declared workload, reminder start p95 ≤3 s and oldest eligible ≤10 s. Pair an idle and mixed 10,000-Note/20-concurrent-request probe; both list and detail p95 must stay below 500 ms and no more than 25% above paired idle. Record host limits, pool metrics, throughput and PostgreSQL connections/activity. |
| BG-04b — recovery and cleanup | All 40 reports complete within 120 s of the start, and a separately injected restart drains ready backlog within 120 s of service recovery. Observe one effect per current occurrence, verify the scope invariants and retire qualification assets. |

Scope: PostgreSQL queue, stock Odoo CRUD, no real push, no recurrence or replacement broker. Retain only bounded, redacted operator evidence. For the current checkpoint and next action, see [implementation status](../docs/implementation-status.md).

For BG-04, verify that all jobs have committed at least ten seconds before the
load clock starts. Use the same 20 authenticated Odoo sessions and the same
request pacing in both web phases, with separately warmed HTTP connections
to avoid the proxy's idle timeout between phases. Record the database CPU
allocation and worker lane counts with each observation. The capacity
thresholds above stay fixed while resources are tuned.

BG-01 through BG-04 passed for the measured reference: three stock Odoo
web workers, four PostgreSQL CPUs, one urgent lane and two bulk lanes.
See the [acceptance decision](../docs/evidence/post-r1/background-execution/qualification-decision.json)
and [operator commands](../docs/operations.md#scheduled-native-job-lanes).

## Follow-up plan for sustained background workloads

Planning review, 7 November 2026. BG-01 through BG-04 are the qualified
baseline. Track active work and evidence in the
[implementation checklist](../docs/implementation-status.md#post-r1-work). This plan
assumes the current single-site Docker deployment and trusted native plugins.
Start with retention and visibility, then make worker deployment and resizing
safe. Recurrence is the first new job feature. Automatic sizing follows
measured demand.

### Scope decisions

| Gap or limit | Recommended scope |
| --- | --- |
| Recurring schedules | Include fixed UTC intervals, pause and resume, and bounded missed occurrences. Add local calendars, daylight-saving rules and cron expressions when a named app needs them. |
| Real push and other remote writes | Include one provider adapter with the first app that needs it. Use the outbox, stable effect IDs and explicit reconciliation. Qualify the actual provider's retry and status semantics before enabling it. |
| Extra pools and workspace concurrency | Keep urgent and bulk initially. Add a pool when a workload needs its own resource budget, provider quota or network access. Keep one attempt per workspace per pool as the default. Qualify higher concurrency only for handlers with explicit independent partitions. |
| Redis or another broker | Keep PostgreSQL as the queue and source of truth. Revisit if sustained tests still miss web or job targets after retention, query tuning and sizing, or if dispatch needs independent multi-host or cross-site operation. |
| Untrusted code | Keep in R2 with a separate threat model and runtime. Native worker credentials, registry and filestore access fit the trusted native execution model. |
| Job history and operator UI | Include bounded retention and a paginated, scoped Operations view using native Odoo patterns. Display safe metadata and outcomes. Keep retry, external settlement and infrastructure actions with independent operator authority. |
| Public job API | Defer generic submission. Let apps expose their own authorized actions and scoped status. A future common API needs its own contract, idempotency and admission rules. |
| Job chains, fan-out, joins and checkpoints | Start with app-owned durable progress and bounded chunks. An import can persist a cursor and enqueue its next chunk in the same fenced transaction. Add bounded fan-out and joins when an app needs them. Evaluate a workflow engine if several apps need durable branching, signals or long-running orchestration. |
| Single-site operation, longer jobs and larger inputs | Keep the single-site target, 30-day schedule horizon, 24-hour validity window, 1-hour attempt ceiling, 16-attempt ceiling and 64 KiB serialized JSON bound. Store large inputs and outputs in scoped application storage and enqueue references. Chunk long work. Expand limits with a workload and a recovery test that exercises them. |

The current API and limits are in [ADR 0061](../docs/architecture-decisions/0061-scheduled-native-jobs-v1.md)
and the [queue implementation](../packages/platform_sdk/modular_platform/durable.py).
Temporal illustrates the additional machinery a workflow engine brings,
including durable event history and checkpoint data across activity attempts.
[Temporal workflows](https://docs.temporal.io/workflows) · [Activity execution](https://docs.temporal.io/tasks).

### Deployment and release ownership

Today Compose brings up edge, Odoo and PostgreSQL. The local operator
launches separate worker containers on the private runtime network. They
use the approved application image, exact database and inventory pins, and
the registry, credentials and filestore needed by trusted native handlers.
The production override defines no worker service. The operator can add
lanes, while a reduction currently calls for draining the worker fleet.
The current launcher allows one to eight lanes per pool, each capped at one
CPU and 768 MiB. Start and drain already share the operator locking path.
[Compose baseline](../deploy/compose.yaml) · [Production override](../deploy/compose-production.yaml) ·
[Job operator](../packages/platform_sdk/modular_platform/job_operator.py).

Aurora's Dokploy deployment offers a precedent for separate web and worker
roles, including dedicated general and log workers. Keep that separation
while binding this platform's workers to the reviewed site and release.
See Aurora's `compose.dokploy.yml` at the pinned revision above.

Keep the first deployment on one Docker host. Make worker roles and desired
counts explicit in the reviewed site profile, with one operator-owned
reconciler. Bind roles to site, database, release, inventory, image and
allowed resource ranges. Keep web and native workers on the same image,
with independent sizing. Workers use private networking, scoped mounts
and readiness checks for pins and dispatch state. Run recurrence as a
separate producer on the same pinned release. Docker documents single-host
Compose and production overrides.
[Docker production guidance](https://docs.docker.com/compose/how-tos/production/).

Before maintenance, pause the scaler and recurring producer, stop new
claims, drain workers and verify the stopped generation. Keep checkpoint,
upgrade, restore and separate resume under existing operator authority.
Recreate roles from new pins after dispatch reopens. Test restore with a
previously emitted occurrence and a previously sent external effect. During
ordinary scale-down, drain selected idle lanes first and give active
attempts a bounded finish policy. The current 45-second shutdown grace is
shorter than some allowed attempts, so qualify the stop path before
automatic downscaling.
[Operator runbook](../docs/operations.md#scheduled-native-job-lanes) ·
[Populated release proof](../docs/evidence/post-r1/background-execution/bg-03-release.json).

If a deployment later needs multiple hosts, keep the same role and metrics
contract. Qualify shared filestore, credentials, connection capacity, worker
identity, shutdown grace and release fencing across hosts. Kubernetes
Deployments with HPA or KEDA are an option where Kubernetes is already used.
Prefer an exported aggregate over raw job table access. KEDA can consume a
numeric PostgreSQL query, and HPA can stabilize downscaling. The platform's
operator still owns release coordination and must verify drain behavior
on the chosen orchestrator.
[KEDA PostgreSQL scaler](https://keda.sh/docs/2.22/scalers/postgresql/) ·
[HPA controls](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) ·
[Pod termination](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/).

### Capacity and automatic scaling

Automatic restart exists. Automatic sizing is a new feature. Start with
fixed counts and an advisor that reports recommended counts and reasons.
Measure ready depth, oldest eligible age, claim-to-finish time including
preparation and apply, arrival and completion rates, active workspace slots,
retry and lease loss, worker startup and drain time, and web and database
headroom. Keep future, expired, held, paused and uncertain work separate
from runnable demand. Export bounded aggregates. The current CLI provides
snapshots and worker logs. Include held and obsolete handler counts
separately because pool metrics currently filter on registered routes.
Keep original eligibility and retry wait separate so a retry does not reset
the apparent end-to-end wait. Measure from the committed claim, including
preparation before the current attempt log. Budget for each lane's native
registry and database connections, including its slot and heartbeat activity.
[Queue metrics](../packages/platform_sdk/modular_platform/job_admin.py) ·
[Worker instrumentation](../packages/platform_sdk/modular_platform/job_supervisor.py).

Use runnable jobs per ready lane for similar-duration work. When costs
vary, estimate **worker-seconds** using observed durations per handler and
version, with reviewed defaults for new or sparsely observed handlers.
Compare ready work plus expected arrivals during the drain window with
seconds available per lane after startup. Account for work already running.
Use oldest eligible age against the pool's start target, and cap growth
using connection usage, PostgreSQL CPU and waits, storage latency and Odoo
web latency. AWS describes sizing backlog per worker from service time and
acceptable queue delay. [AWS queue-based sizing](https://docs.aws.amazon.com/autoscaling/ec2/userguide/scale-sqs-queue-cli.html).

For example, 120 ready reports averaging two seconds represent 240
worker-seconds. A 60-second drain target with a 10-second startup reserve
suggests five lanes before arrivals and active work are considered. If
the reports span two workspaces, the current cap permits two concurrent
attempts. The advisor should report why the target is unreachable. Adding
lanes helps when other workspaces have available slots. For one hot
workspace, measure the handler and qualify independent partitions before
raising concurrency. Test fairness with more than the current 64 workspace
candidates and qualify the session-held slot lock under connection loss.
[Workspace lock](../packages/platform_sdk/modular_platform/job_supervisor.py:83) ·
[Candidate scan](../packages/platform_sdk/modular_platform/durable.py:250).

Keep urgent workers warm. The reference reminder p95 was 2.805 seconds
against a three-second target. Start bulk with a warm minimum and reviewed
maximum. Consider scale-to-zero only after measuring the wake-up delay.
For predictable spikes, compare prewarming capacity with reactive growth.
If polling becomes a measurable cost, compare adaptive backoff and a
PostgreSQL notification as a wake-up hint. Keep a timed recheck for jobs
becoming eligible and for workers reconnecting after missed notifications.
Offer opt-in bulk autoscaling after manual resizing and the advisor pass.
Use sustained signals, rate-limited growth and slower downscaling. Hold and
alert on stale metrics or database saturation. Serialize resizing with
release operations and keep the controller unable to reopen dispatch.
Compare fixed, count-based and estimated-work policies against identical
load. Prefer the simplest policy that meets the agreed service and resource
targets. [Qualified mixed load](../docs/evidence/post-r1/background-execution/bg-04-qualified.json) ·
[PostgreSQL notifications](https://www.postgresql.org/docs/16/sql-notify.html) ·
[Scaling stabilization](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/#stabilization-window).

### Implementation gates and acceptance

- [x] **BX-01. Retention and visibility.** Size history from peak arrival
  rate, recovery horizon and deduplication requirements. The lifecycle
  snapshot has a 100,000-row bound per dispatch table, and job reconciliation
  separately counts all jobs. At 10,000 retained jobs per day, the job table
  alone reaches that bound in ten days. Include event and outbox history. Specify
  separate retention for full payloads, safe status, scoped deduplication
  keys and external-effect receipts. Preserve semantic digests within the
  approved replay window. Move eligible terminal history out of the live
  lifecycle scan with its deduplication record written atomically. Keep held
  and uncertain work visible and retain external evidence across restore.
  Define the result a duplicate receives after full job data has expired.
  Start with bounded resumable batches
  and measured indexes. Time partitioning complicates global deduplication
  because partitioned unique keys must include the partition key. Prove
  duplicate submission after pruning, enqueue and cleanup races, crash,
  upgrade and restore with realistic historical totals above the old cap.
  Measure lock duration and web latency. Add paginated scoped status and
  aggregate alerts before action buttons.
  [Lifecycle bound](../packages/platform_sdk/modular_platform/dispatch_lifecycle.py:182) ·
  [PostgreSQL partitioning limits](https://www.postgresql.org/docs/16/ddl-partitioning.html#DDL-PARTITIONING-DECLARATIVE-LIMITATIONS) ·
  [Vacuum and space reuse](https://www.postgresql.org/docs/16/routine-vacuuming.html).
- [x] **BX-02. Managed deployment and manual resizing.** Reproduce roles from
  a reviewed site profile. Add per-lane drain and visible desired versus
  ready counts under existing locks. Test wrong pins, partial starts,
  connection loss, resizing with active jobs, stale claim refusal and
  a resize racing an upgrade. Measure connection and resource usage.
- [x] **BX-03. Recurrence.** Store a versioned schedule and cursor under a
  scoped service identity. Advance the cursor and enqueue in one transaction
  with a stable key for the schedule and nominal occurrence. Keep occurrence
  identity stable across credential rotation and schedule edits. Start with
  skip or coalesce-latest after downtime, and one outstanding occurrence per
  schedule. Require a replay window and batch cap before supporting full
  catch-up. Emit one-off jobs only inside their scheduling horizon. Guarded
  web startup requires zero Odoo cron threads, so use a separate producer
  under the dispatch fence. Test duplicate ticks, downtime, revocation,
  edits, overlap, maintenance and restore of a previously emitted occurrence.
  Qualified by [the BX-03 decision](../docs/evidence/post-r1/background-execution/bx-03-decision.json).
  [Guarded startup](../packages/platform_sdk/modular_platform/worker_start.py:52) ·
  [Odoo scheduled actions](https://www.odoo.com/documentation/19.0/developer/reference/backend/actions.html#scheduled-actions-ir-cron) ·
  [CronJob catch-up and overlap](https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/).
- [x] **BX-04. Load and scaling.** After BX-01 and BX-02, repeat BG-04 and
  test sustained arrivals for the first heavy app. Fix the workload, queue
  wait, web p95 and DB headroom targets before running. Include one hot
  workspace, many workspaces, variable runtimes, process loss, database
  saturation and stale metrics. Compare advisor recommendations with actual
  drain time, expired work, and worker-hours. Exercise fast bursts where a
  new lane would arrive after the useful start window. Enable automatic bulk sizing only if
  it improves the result and passes scale-down, rollback and release drills.
  Include recurring bursts after BX-03. Reassess pools and brokers against
  measured gaps. A broker would still need an outbox publisher,
  acknowledgments, deduplication and recovery around the handoff.
  [RabbitMQ delivery reliability](https://www.rabbitmq.com/docs/reliability).
- [x] **BX-05. App-driven extensions.** Select the first app that needs remote
  delivery or resumable chunks. For push, use an outbox consumer with scoped
  provider access, rate limits and distinct accepted, delivered, rejected and
  unknown outcomes. Qualify response loss, duplicate receipts, revocation,
  provider key lifetime and restore. For chunks, prove cursor and successor
  enqueue atomicity, cancellation and version compatibility. Qualify bounded
  fan-out when needed and propose common orchestration or public API only
  once a shared requirement is clear.
  [FCM acceptance and delivery](https://firebase.google.com/docs/cloud-messaging/understand-delivery) ·
  [Provider idempotency example](https://docs.stripe.com/api/idempotent_requests).

The open sizing inputs are the first app's arrival rate, burst and wait
target, the desired retention and restore window, and the deployment
topology. Retention and visibility can be developed on disposable sites
while those inputs are collected.
