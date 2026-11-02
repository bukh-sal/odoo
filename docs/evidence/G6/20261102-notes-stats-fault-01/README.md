# Canonical worker timeout and crash checks

Qualified on the existing disposable G6 profile: native config18/dispatch88,
BB1 image, core/SDK0.1.16, NotesStats0.1.0, metadata DocumentStats0.1.1.
Product source is unchanged from `afc7ab57`. See the preceding native install
and positive remote evidence for immutable image/inventory/source provenance.

`fault.py` captures a fresh consistent 17-table baseline and independently
attests the exact running worker before each case. Every mutation is preceded
by a private durable marker. Run actions separately in the documented order:
`baseline`, `fault`, `enqueue`, `run`, `verify_down`, `recover`, `verify_up`.
Both cases are completed; **do not replay them** against the now-populated site.

| Case | Actual failure | Ordinary runner | Recovery |
| --- | --- | --- | --- |
| Paused worker | One-attempt dead letter, DEADLINE_EXCEEDED | 19.69 seconds total | Unpause same process; exact before/after identity and start time |
| SIGKILL | Confirmed container exit137; one-attempt dead letter, DEPENDENCY_UNAVAILABLE | 14.00 seconds total | Separate start of same container; fresh image/key/scope/address/publication attestation |

During each outage, original Alice could read the Note and job status, obtain
connector context, and load native Odoo list/form definitions in A/B/C. After an
explicit fresh operator planning-profile publication, the normal installed-manager
HTTP endpoint reported degraded provider health. Separate recovery and fresh
publication returned health to healthy. Feature enablement and independent approval
were unchanged; health did not substitute for either.

All old20/21 jobs and every row of the other16 baseline tables remained exact.
The two failed jobs stayed terminal with no result after worker recovery. Final
queue:22 terminal jobs,8 completed/12 dead-letter/2 cancelled;29 Notes unchanged.
No new persistent Docker container/image/volume was created; ordinary one-shot
job helpers auto-remove. The same active worker and public configuration volume
remain needed. No pruning or unrelated cleanup occurred.

The initial timeout `verify_down` assertion expected the planning reader's
`unavailable` label at the manager boundary. Existing `manager_views.py` maps
that state to `degraded`; the real response was correct. The harness assertion
was corrected, and a distinct read-only continuation preserved the initial logs.
No job enqueue, runner, or fault injection was repeated. Product source unchanged.

This qualifies backend survival/degraded status only. It does not qualify browser
rendering, duplicate/scoped/in-flight cases, uncertain external effects/recovery,
changed-worker-image compatibility or complete SVC-02/G6/G7. Acceptance remains
92/99; weighted progress remains roughly89%.
