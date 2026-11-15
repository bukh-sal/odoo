# Final regression: observation-test clock reconciliation

Activated16November2026 after the one frozen source40 canonical run finished.
Original run:981tests,978pass, one failure, two existing skips; exit1 after
5080.5s. Its complete log/process/source receipts remain unchanged under
`.local/ui-final-canonical040-01/`. The failure is not accepted as green and D06
remains open.

## Confirmed cause

`test_operation_progress.ProgressTests.test_actual_context_returns_without_claiming_journal_success`
reads a real observing record, derives an artificial future `now` from that
record's timestamp, then rereads the file while its actual five-second heartbeat
thread can advance it. The assertion expected `stale`; the actual result was
`observing`. A newer heartbeat can legitimately be less than20seconds old at
the supplied artificial time. Private-directory/OS checks make this interleaving
possible; their execution time is not a product failure or an environmental waiver.

`tools/operation_progress.py` intentionally reads the latest bound record. Its
observation is not execution authority, journal completion or permission to
retry. The current behavior should remain intact.

## Bounded correction before another final run

1. Preserve the failed canonical log, exact trace, exit and frozen-source map.
   Verify executable/app sources remained exact through that run. No runtime
   mutation, apply or build replay is part of this work.
2. Change only the test's clock during its actual context/thread/private-file
   checks. A fixed injected `_now` makes the stale/past/returned assertions refer
   to one controlled timestamp; keep real writer thread, OS locks/private files,
   monotonic elapsed behavior and every original assertion.
3. Add a counterexample using a valid newer heartbeat record after its real
   writer has joined. At a time derived from the older heartbeat, the newer
   record must remain observing; only its own age crosses the stale threshold.
   Preserve clock-changed and non-authoritative outcome semantics. No sleeps,
   longer timeout, removed assertion, production hook or retry waiver.
4. Run the focused observation module. Independently compare production files,
   the actual current candidate curated-input maps and the five private app
   heads/archives. A test-only change needs no product identity or image rebuild
   when the actual source-map comparison proves shipped bytes unchanged.
5. Commit the test/evidence correction, freeze the new test source and run the
   canonical `tests/run_host_regression.py` once in a fresh private output root.
   Use the same isolated interpreter and verified process-local ripgrep. Observe
   its specific process to terminal; preserve both full runs, never relabel the
   failed one. Only a real final result and original-card audit can accept D06.

No executable/test edits occur while either canonical process is running. Only
the now-terminal first run permits this correction. Original UI-D03/D04/D05
acceptance, current installed40 browser evidence, protected main/demos and all
recovery/business material remain preserved.
