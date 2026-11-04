# ADR0058: bind kit source to explicit reproduced application inputs

Date:2026-11-04. Status: implementation/source tests passed; actual final kit
assembly remains pending a corrected qualified application candidate.

The first producer selected an application from the hardcoded core23 reproduction
receipt. Reusing that producer for a later release could silently retain14de
while archiving newer application sources. A source-only draft refresh also lacked
an application/source compatibility guard. These are release provenance gaps,
not changes to live executor approval or application contracts.

Require independently selected `--application-build` and
`--application-reproduction` receipts for assembly and draft source refresh. The
reproduction must report the complete passed no-cache declared-inventory profile
and BOOT-02, immutable image/base/inventory IDs and all required comparisons.
The candidate build must match its reference image, inventory and dependency
base. Verify the complete recorded build-source path set and every current file
hash using the same directory/file selection as the candidate builder. Refuse
omitted/new/changed source files, path aliases/links and malformed receipts.
Documentation and release helpers outside the build-source set may change without
forcing another application version. No receipt field authorizes execution or
authenticates its producer; operators still select and review the evidence.

Assembly validates these inputs before creating an output directory or making a
Docker call, retains both exact receipt files in the checksummed kit, and checks
the actual selected image inventory before export. Draft source refresh also
requires the kit's existing application/base/inventory to match; it cannot change
images or make an old image current by replacing source.zip. The existing source
refresh remains an unsealed-kit operation; final privacy/provenance/clean install
checks still apply. Unknown or partial directories are never reset on failure.

Nine focused tests cover valid identity/hash binding, every required comparison,
mutable/disagreeing image identity, changed/new/omitted source, bad paths,
unqualified results, duplicate fields and bounded receipt size. The actual old
core23 receipt is expected to fail against the current changed build-source set;
do not build or deploy a known residual image merely to pass this guard.

No new Docker asset, native schema, public SDK/DTO, permissions or worker authority
is introduced. Preserve old kit/evidence at their historical scope. Actual final
image reproduction, kit refresh/assembly/privacy and developer installation remain
G7 requirements.
