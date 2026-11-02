# Actual reference metadata restore and current-authority resume

F-01e2, §§10.3/10.5,13.4,14.2/14.6. This is stateless-reference recovery
qualification, not JOB-03 non-idempotent external-effect evidence or a G6 pass.
Product source remains `b1bd4a36`; native imageBB1/coreSDK0.1.16/inventory4833
unchanged. No public contract or runtime source was edited.

1. Fresh baseline:28 terminal jobs,30 Notes,49 outbox events, current native
   modules/schema and canonical independently managed worker05/config3/pub5.
2. New normal HTTP manager suspension request `d0b079f4-415d-4ea5-b777-f543ae70e752`,
   exact hash `af4e8219…`, was independently reconstructed/reviewed/approved.
   A host-only fault wrapper raised after the real metadata child exited0 and
   committed its provider-feature/policy change. The executor entered
   recovery_required with traffic closed. Old jobs and unrelated tracked rows
   stayed exact; the external process/approval were unchanged.
3. Separate reviewed restore created
   `mp_disposable_r0_r1_restore_d0b079f4415d4ea5b777f543ae70e752`, fresh native
   epoch19. It retained the failed DB and restored the checkpoint feature state.
   Closed verification proved all30 Notes,28 old job outcomes/input/key/attempt/
   deadline/result, native schema/module rows, metadata, event history, current
   native authority/private authentication and48 files. Only documented queue
   epoch and global security-policy cache generations changed. The real edge
   was stopped and dispatch paused. No keys/OS approval were copied from the DB.
4. After an initial resume review, a separate exact operator publication revoked
   endpoint3→4/document5→6. The worker and all17 tracked tables stayed unchanged.
   While the review was still unexpired, the actual verifier rejected its changed
   effects/observation, and normal CLI resume returned2. Traffic/dispatch stayed
   closed. This revocation happened **after** the SQL restore; it proves the
   current-approval fence at resume, not a different timing scenario.
5. The separate operator provisioned new immutable issuer/public references,
   explicitly stopped the same worker, atomically changed its public-only key/
   config3→5, restarted and attested it, then independently reviewed/published
   enabled endpoint5/document7. The metadata installer did not control that
   runtime transition. No signing key reached the worker or HTTP app.
6. Four actual worker requests accepted the new key, rejected the retired signing
   key under the current key ID, rejected the retired key ID, and rejected the
   old endpoint generation. The current issuer also denied the retired reference.
   A new distinct resume decision bound current publication7 before traffic opened.
7. Resumed native A/B/C list/form definitions and saved Note reads passed. Old
   epoch18 gateway/native pins and the retired operation were refused. A new
   ordinary independently configured original-Alice job completed once using
   current endpoint/key approval with exact revision2 statistics. Prior28 jobs
   and the other16 tracked tables stayed exact.

Current native19/dispatch98,29 terminal jobs (11 completed/16 dead-letter/2
cancelled),30 Notes/49 outbox/35 subscriptions/251 deliveries/3 consumptions/
1 consumer state. Worker05 same image/container/scope/mounts; its later restart
and new public key were explicit operator actions after the closed DB proof.
Current public config5,publication7,key ID `recovery19-key`; old refs remain
protected historical material and cannot issue for current approval.

Cleanup archived diagnostics privately and removed22 exact owned exited
containers, preserving active host/DB/edge/worker, failed DB and checkpoint
files/images/volumes. No new image/volume, global prune or daemon restart.

The initial harness import used a nonexistent module and failed before baseline;
it was corrected to `restore_executor`. An extra edge assertion was added to the
fault script after that process loaded its code; it is not claimed as executed
there. The subsequent closed verifier actually inspected the stopped edge.
All mutations and reviews have private before-action markers. This completed
once; never replay its operation, restore, key updates or jobs.

Limits: terminal-history stateless reference profile; no remote non-idempotent
effect/reconciliation proof, no post-checkpoint pre-SQL-restore revocation test,
no changed-worker-image transition or browser rendering claim. JOB-03, SVC-05,
SVC-02 UI and G7 remain required. Acceptance94/99; rough progress89% unchanged.
