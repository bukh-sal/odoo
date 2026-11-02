# SVC05: changed-image qualification complete for the R1 reference profile

`qualification.json` audits the previous real transition/failure/recovery records
and the current successful path against the installed image, data and authority.
It qualifies SVC05 (spec14.6, shared10.5/11.6/23). It does not pass G6 or G7.

The operator separately stopped/reconfigured/restarted the same new worker06,
retaining image548202/key19/runtime/mounts, to advance public configuration7->9.
`public-config9.json` shows host data stayed exact while approval remained revoked.
`runtime-review.json` and `runtime-publication.json` record fresh independent
publication11/endpoint9; no old approval was restored.

New normal HTTP manager requests then completed through independent
import/reconstruction/review/exact approval and the ordinary executor:

| Operation | ID | Result |
| --- | --- | --- |
| Metadata0.1.1->0.1.2 upgrade | `115154b6-fa14-4883-a969-01b579b2f344` | Native23/control111, provider still suspended |
| Separate enable | `782b4010-af48-4941-a1fc-e7507e24254e` | Native23/control114, provider enabled |

Both preservation reports verify29old job outcomes/inputs/attempts/results,
30Notes, all other tracked data/native/auth/history, unchanged native schema and
module state,48checkpoint files, and unchanged physical worker/publication11.
Only reviewed metadata/feature/policy/queue epochs changed. Both operations
returned to the strict default reference profile; the temporary transition
context is no longer needed. The original failed plan5edc remains revoked.

`current-credentials.json` records real requests to the current worker: current
generation9 accepts200, old7 refuses403, foreign audience401, foreign workspace403,
and retired signing key/currentkid401. The current authority also refuses the
retired issuer reference. Tokens/key material are not stored in public evidence.

`ordinary-remote-job.json` records the ordinary original-Alice gateway/CLI job
`c7115fe8-b465-49a9-bb7a-b9570fa6e306`: completed once, revision2,50characters,
7words/1line. Native A/B/C views and completed HTTP operation mirrors passed;
all29old outcomes and the other16tables stayed exact. Current total is30terminal
jobs (12completed/16dead_letter/2cancelled). Provider and manager report healthy.

`unknown-effect-refusal.json` is an installed native regression with an actual
transactional fence and uncertain job state. Dispatch enable refuses unknown
effects; rollback restores every job/control/table value. It dispatches no job and
performs no external effect. The earlier real counter/crash/lease/nonretry fixture
remains the separate JOB03 evidence.

`retirement.json` records22exact terminal containers removed, including two old
hosts, seven receipt-bound observations and the obsolete worker05. Its public-only
volume was archived and removed after verifying no other mounts. Current worker06,
host/database/edge/authority11/config9 remain; old image1d is retained as the actual
checkpoint/derivation base. No global prune, forced removal or unknown reset.

Limits: image548202 is a compatible release-label change with exactly the old1d
runtime code/OS/Python layers. No API-major/storage migration, arbitrary external
rollback, native sandbox or generic effect reconciliation is claimed. The earlier
independent revocation10 was injected after the closed SQL restore, invalidated
the unexpired review, and required a fresh resume. Browser rendering remains
deferred by user request. Required next: minimal Notes detail action/degraded UI
(SVC02), complete G6 integration and the full G7/ID03/UI09/release qualification.
