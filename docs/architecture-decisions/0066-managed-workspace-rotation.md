# ADR0066. Rotate managed workspace candidates

Status:qualified, including core44 load and fresh recovery. Two30-job hot workspaces
consumed all60 claims before any of68 equal-eligibility peers started.
Per-workspace concurrency alone did not provide fair service.

Managed lanes rotate the candidate workspace ID after each successful selection
reservation. Keep the existing64-candidate bound, workspace session slot,
registered route filter and FIFO job order inside each workspace. A small
site/pool-specific parameter in the existing native configuration table stores
the release epoch, last selected workspace and a random comparison token.
Use a separate short READ COMMITTED transaction and compare-and-swap before
claiming; stale selectors retry from fresh metadata. Never hold this hint's
write lock through native authorization, preparation, compute or apply.

The hint is performance metadata. It grants no workspace, plugin, credential,
dispatch or job authority. Reservation checks current release and enabled
dispatch; normal claim/prepare/apply checks remain authoritative. A lost process
or failed claim may consume a turn. A malformed bounded value or changed release
resets selection to the start of the ring with an exact atomic replacement.
The database checkpoint naturally includes the hint, and a fresh restored epoch
may reset it. It never rewinds a cursor, creates a job or replays an effect.

Legacy private SQL callers retain their original default selection order;
reviewed managed lanes opt into rotation. This is not a hostile-plugin sandbox
or a hard compute-execution limit after lease loss. Session-lock loss, lease
reclaim and stale apply still require separate BX-04 qualification.

Qualify atomic reservation/rollback, stale selectors, scope keys, pause/release
refusal and ring wrap in PostgreSQL, then the same native128-job baseline and
process restart. Keep all prior failed evidence. Recheck required load/headroom
where candidate selection changes affect its measured boundary.
