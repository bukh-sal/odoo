# Fresh authorization when accepting external analysis

F-01d prerequisite G6-EXTERNAL-FINALIZE-01, spec §§11.6, 13, 14.6; ADR0034.

`qualification.json` / attempt02 records 22 passing real native/PG source tests.
Candidate core/connector modules are loaded into an isolated process in the
existing application container. The installed HTTP/runner modules are unchanged.
All fixture writes roll back; 19 metadata/authority/queue/event/business tables
have exact before/after row hashes. Sequence counters may advance. All protected
deployment configuration hashes remain exact. No Docker asset was created.

The detached computation now returns a private `{statistics, authority_digest}`
wrapper. The digest binds the full worker authority snapshot (endpoint, egress,
publication generation, key identity/fingerprint) and current provider binding.
It does not cross the worker API or appear in public results. Native computation
rechecks this binding around remote I/O. The reusable authorization reader checks
current actor scope, binding/provider/feature/grants and fresh protected authority.
It rereads the publication after native authorization to reject intervening drift.

Final apply uses that reader in the existing freshly authorized `finish_one`
transaction and compares the computed fingerprint. It does not open another
cursor and attempt to acquire its own already-held job lock. It performs no
network operation or signing. Original actor/resource/revision gates remain.
Native authority locks remain held through the database outcome transaction.
The filesystem publication and PostgreSQL commit are not a distributed atomic
transaction; no such guarantee is claimed.

Tests cover successful read-only completion, stale Note revision, original actor
revocation, external grant revocation, feature suspension, unregister, unavailable
or validly replaced binding, endpoint revocation, publication generation/key/egress
changes, publication drift during native authorization, and rejection of the old
statistics-only computed shape. Public status remains readable after worker
revocation/key removal under current Note/connector authority. Two compute-wrapper
checks substitute transport/fresh-snapshot IO explicitly; no actual remote request
is claimed. Other checks use actual native authority, registered job finalization
and temporary real authority/public-key files. Those files are fixtures, not
independent operator approval or image attestation.

Attempt01 passed19 cases; its binding-replacement fixture tried to mutate an
immutable native binding identity and was correctly refused by the existing
model guard. Attempt02 replaces the binding through unlink/create in the rollback
fixture, exercises the intended valid replacement and passes all22 cases. No
production guard was relaxed. The aggregate row-restoration report now independently
compares the whole suite's before/after state instead of deriving restoration from
the test success flag.

`packages.json` proves deterministic archive validation/composition, shipped public
schema equality and unchanged previous three native archives. The new computed
wrapper is private, so frozen public DTOs are unchanged (94files/eight rows pass).
The unshipped connector now requires platform0.1.13; the current installed0.1.12
cannot satisfy that new helper requirement. No connector/provider is installed.
Earlier source-only connector/artifact reports remain historical, superseded for
these changed files; native installed JOB01/02 paths did not change.

Next: close the queue-bearing native feature lifecycle prerequisite, produce the
coherent core/SDK.13 image, and qualify real reviewed metadata registration,
connector install, remote/degraded behavior and external lifecycle/recovery.
Changed-worker-image transition remains a separate required compatibility boundary.
No SVC/recovery acceptance credit is awarded by these source tests.
