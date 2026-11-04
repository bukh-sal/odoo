# ADR0056: bounded independent executor observation

Date:2026-11-04. Status: accepted and qualified for the supported operator CLI.
Active leaf G-01c4, spec24.1–24.3.

The independent journal preserves phase timestamps and possible-effect fences,
but a killed CLI can leave its last state `running` indefinitely. Application
progress is a best-effort mirror and the app intentionally stops during native
maintenance. Its stale flag cannot supply an independent executor heartbeat.

Add a small operator-tool observation wrapper to the supported CLI apply,
restore and resume commands. Write an atomic private observation every5seconds,
and expose it through independent `operations show`. After20seconds without an
observation, report stale. Distinguish observer activity, last journal phase,
CLI return/exception and actual journal outcome. A fresh heartbeat means the
wrapper's observation thread ran; it does not prove business work advanced.
Wall-clock changes yield uncertainty. Legacy operations without a heartbeat
report not recorded. No PID-only death assertion, takeover, timeout-based
approval, replay, remote undo or automatic recovery.

Use the existing owner-protected store and a separate process lock to serialize
observation writers. Existing deployment/site locks, exact review, approval,
revalidation and journal semantics remain the only mutation controls. Diagnostic
failure cannot turn an actual executor outcome into success or retry it. Bound
each observation to its operation/plan hash and a unique invocation ID; publish
no credentials or input/document bodies. No background daemon or new Docker
assets are needed.

This is an additive private operator CLI diagnostic, outside the frozen public
operations HTTP DTO. Keep SDK/app image/public schemas unchanged. Qualify real
separate-process heartbeat and forced-death staleness, concurrent-writer refusal,
return/exception distinctions, malformed/wrong-plan records, and current journal
readback. Do not replay a completed lifecycle operation to test a diagnostic.
Record updated operator-tool bytes in the final source kit; current immutable
application/worker identities remain qualified separately.

Qualification: `../evidence/G7/20261104-observability-01/progress-qualification.json`.
Actual separate-process pulse advanced5.031seconds; forced death became stale
19.860seconds after the kill, measured against the last observation's20second
age. Concurrent writer refused; return/exception distinct.19affected unit tests
passed. Current completed reference operation readback preserved the real journal
and reported not recorded, without creating an observation directory. An initial
Windows venv-launcher PID mismatch is retained; the final probe used the exact
selected base interpreter and selected environment packages. No lifecycle replay
or Docker assets. Current source-kit update and full G7 remain separate.
