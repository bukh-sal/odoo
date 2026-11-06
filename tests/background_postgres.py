"""Opt-in durable schedule integration against the isolated BG PostgreSQL service."""
from datetime import datetime, timedelta, timezone
import json
import time
from uuid import uuid4

import psycopg2
from modular_platform import durable as q


DDL = """
CREATE TEMP TABLE mp_dispatch_control (
    site_id varchar PRIMARY KEY, release_digest varchar NOT NULL, state varchar NOT NULL, generation int NOT NULL
);
CREATE TEMP TABLE mp_job (
    id serial PRIMARY KEY, public_id varchar UNIQUE NOT NULL, site_id varchar NOT NULL,
    workspace_id int NOT NULL, actor_id int NOT NULL, installation_id int NOT NULL,
    handler varchar NOT NULL, handler_version int NOT NULL, idempotency_key varchar NOT NULL,
    release_digest varchar NOT NULL, payload jsonb NOT NULL, input_digest varchar NOT NULL,
    effect_mode varchar NOT NULL, state varchar NOT NULL, attempts int NOT NULL,
    max_attempts int NOT NULL, claim_generation int NOT NULL, dispatch_generation int NOT NULL,
    lease_owner varchar, lease_until timestamp, available_at timestamp NOT NULL, deadline_at timestamp NOT NULL,
    cancel_requested boolean NOT NULL, effect_started boolean NOT NULL, progress int NOT NULL,
    created_at timestamp NOT NULL, finished_at timestamp, result jsonb, error_code varchar,
    UNIQUE (site_id,workspace_id,actor_id,installation_id,handler,handler_version,idempotency_key)
);
CREATE TEMP TABLE bg_effect (key varchar PRIMARY KEY);
"""


def ident():
    return str(uuid4())


def expect(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return
    raise AssertionError(f"Expected {exc.__name__}")


def run():
    connection = psycopg2.connect(host="mp-bg-qual-pg", user="postgres", dbname="postgres", connect_timeout=3)
    site, release, handler = ident(), "sha256:" + "a" * 64, "org.example.bg:test"
    scope = q.DispatchScope(site, 1, 2, 3, release)
    findings = []
    with connection.cursor() as cr:
        cr.execute(DDL)
        q.set_control(cr, site, release, "enabled")
        connection.commit()

        def schedule(delay=0, window=15, budget=2):
            now = datetime.now(timezone.utc) + timedelta(seconds=delay)
            return q.JobSchedule(now, now + timedelta(seconds=window), budget)

        def enqueue(key, timing, **options):
            return q.enqueue(cr, scope, handler, 1, {"schema_version": 2, "schedule": timing.wire()},
                             key, schedule=timing, **options)

        def claim(lease=30):
            return q.claim(cr, site, release, ident(), [handler], lease_seconds=lease)

        def row(job):
            cr.execute("SELECT state,lease_until,attempts,progress,error_code FROM mp_job WHERE public_id=%s", [job])
            return cr.fetchone()

        lost = enqueue("rolled_back", schedule())
        connection.rollback()
        assert row(lost) is None
        findings.append("enqueue_rolled_back")
        timing = schedule(1.0)
        job = enqueue("scheduled", timing)
        assert enqueue("scheduled", timing) == job
        expect(q.QueueError, enqueue, "scheduled", schedule(2))
        assert claim() is None
        connection.commit()
        time.sleep(1.05)
        active = claim(1)
        assert active.job_id == job and row(job)[1] < active.budget_until
        q.heartbeat(cr, active, lease_seconds=30, progress=37)
        q.heartbeat(cr, active, lease_seconds=30, progress=21)
        assert row(job)[1:4] == (active.budget_until, 1, 37)
        assert not q.cancel_scheduled(cr, job, actor_id=2, workspace_id=7)
        assert q.cancel_scheduled(cr, job, actor_id=2, workspace_id=1)
        assert row(job)[0] == "cancelled"
        expect(q.ClaimLost, q.run_fenced, cr, active, lambda _: None)
        findings.extend(["stable_dedup", "no_early_claim", "heartbeat_budget", "cancel_fences_claim"])

        expiring = enqueue("expiry", schedule(window=1, budget=1))
        connection.commit()
        time.sleep(1.05)
        assert claim() is None and row(expiring)[4] == "DEADLINE_EXCEEDED"
        findings.append("expiry_visible")

        retry = enqueue("retry", schedule())
        old = claim(1)
        assert old.job_id == retry
        connection.commit()
        time.sleep(1.05)
        new = claim()
        assert new.job_id == retry and new.generation > old.generation
        expect(q.ClaimLost, q.run_fenced, cr, old, lambda _: None)
        q.run_fenced(cr, new, lambda _: cr.execute("INSERT INTO bg_effect VALUES (%s)", [retry]) or {})
        assert row(retry)[0] == "completed"
        findings.append("reclaimed_generation_fenced")

        ambiguous = enqueue("unknown", schedule(), effect_mode="reconcile")
        started = claim()
        assert started.job_id == ambiguous
        q.effect_started(cr, started)
        assert q.cancel_scheduled(cr, ambiguous, actor_id=2, workspace_id=1)
        assert row(ambiguous)[0] == "outcome_unknown" and claim() is None
        findings.append("possible_external_effect_remains_unknown")
    connection.close()
    return findings


if __name__ == "__main__":
    print(json.dumps({"observed": run()}))
