# Notes analysis reference connector

This optional native connector reads a saved Note **body** through its declared
`documents` service binding and sends its revision-bound snapshot to the separately
operated statistics worker through a durable job. It adds an abstract Odoo service
model, no data table, Note fields, record screen, or Canvas feature.

`org.example.notes_stats.jobs` API1.0 provides:

- `analyze({note_id, expected_revision})` returns `{job: <job status>}` after enqueue.
  Browser clients must supply a new gateway idempotency key for each explicit
  request and retain that key across retries. Saved gateway responses return the
  original job; worker retries retain the job ID as their operation ID.
- `status({note_id})` returns `{job: null}` or the latest job for this Note, current
  actor, connector installation and workspace. It first reauthorizes the Note;
  it does not accept arbitrary job IDs or reveal other actors' jobs.

Completed job results are `{note_id, revision, statistics: {characters, words,
lines}}`. Statistics describe the saved body at that revision. A later Note edit
requires a fresh explicit request; a UI must compare the result revision before
displaying it as current. No Note content is edited by analysis. The private job
payload stores the Note identity/revision, not the body; the body snapshot exists
only in detached computation and the worker request. Finalization rechecks the
current original actor, grants, availability, resource and revision.

The `stats` binding and external plugin dependency are optional. Missing or revoked
worker authority must produce an unavailable/degraded analysis outcome while base
Notes remains usable. Installing this connector does not install or launch a worker.
Core/SDK0.1.13 or newer and Notes0.2.7 or newer are required. R1 qualification
still needs the reviewed immutable deployment, independent endpoint publication,
committed remote job integration and minimal native-detail action qualification.
