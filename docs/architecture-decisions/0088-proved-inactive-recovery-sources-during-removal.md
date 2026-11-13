# ADR 0088: Proved inactive recovery sources during source removal

Status: installed correctness passes, 13 November 2026; timing remediation open.
The first actual removal preserved all source/history but324.578s exceeds300s.
The successful command is not replayed or counted as a budget pass.

Normal fresh checkpoint recovery deliberately retains its source database. The
original source-removal observer required every non-template database to be a
configured live site, plus an empty maintenance database. That intentionally
strict profile blocks source removal after a successful recovery, even when
the retained sources have already undergone a normal native uninstall. Dropping
or hiding those databases would violate recovery retention and completeness.

Extend the private host observation only through independently owned recovery
history. The independent validator supplies its OS-owned staging store; no
artifact, browser, database field, path argument or name pattern nominates an
exception. Without that store, the original strict behavior remains unchanged.

An extra database qualifies only as an unambiguous original source of a resumed,
known native completed-checkpoint recovery. Verify original completed destructive
uninstall history, review-bound source replacement/checkpoint, checkpoint bytes,
verified restoration result, same project/deployment/site and exact current image.
Unknown, partial, different-image, external/recurring, failed-operation-only or
corrupt histories remain unsupported. Retained is an operating role, not deletion.

Independently observe the exact stopped successful source worker, no other live
managed worker except the current pin, no source maintenance child or client,
exact executable inventory and the source's published release. Reuse the fixed
offline observer and unchanged native/site removal validator for every package
in the current base image. Sources must have uninstalled native addons, removed
metadata, suspended features, revoked grants and no live bindings. Recheck history,
source metadata, client/worker state and actual database inventory for drift.

Reuse the freshly verified current runtime only within one observation when
all sources are proved to have that exact immutable image and inventory digest.
Each source still receives two fixed read-only SQL observations; the current
observer still verifies runtime before reading sites. This removes redundant
offline scans, not a source/authority check. Missing/tampered/wrong image or
inventory witnesses refuse. No cross-call runtime, ACL or identity cache is used.

Only after that proof, apply the unchanged strict live-sharing validator to the
configured live databases plus maintenance. Return the retained-source proof
separately for operator evidence. Independent reconstruction repeats it at normal
registration, approval and execution boundaries; completeness alone authorizes
no source removal. Current-site inertness, exact staged image/subtraction, scoped
targets, checkpoint and exact approval remain required. Never connect to an
unowned database to explore whether it can be ignored.

No SQL writes, app imports, database moves/deletion, live code unload, manual
authority repair or general archival framework is introduced. Historical images,
catalog archives, checkpoints and source data remain retained and recoverable
under their recorded limits. There is no all-host byte-erasure claim.

This intentionally expands one private host completeness profile. Public wire
schemas and runtime maintenance/hash guards remain unchanged. Retained images
keep their original bytes/source identities; qualified host source is recorded
separately. Shipping changed SDK bytes requires a future identified build.
Different-image/legacy retained-source support requires its own source, effect,
ownership and recovery qualification, rather than a broader name-based waiver.
