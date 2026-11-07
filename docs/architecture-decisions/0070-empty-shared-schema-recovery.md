# ADR0070. Recover the exact skipped empty-schema introduction

Qualified by CF-04: both original45 and final46 fault/fresh-restore/separate-resume
cases passed; peer native workflows and16 reports stayed useful in each outage.

CF-04 upgraded populated Maintenance from the recomposed common-policy core30
baseline to core45. The same upgrade on Aurora reached publication, then the
controlled fault left traffic closed and the failed app stopped. Independent
recovery correctly refused the failed schema: the existing allowlist recognized
30-to31 identity,32-to33 event history and36-to37 recurrence separately, not
their combined introduction. No restore review or restore mutation occurred.

Add only exact native core30-to45 and30-to46 version pairs to the private
empty-introduction guard. Require the ordinary independently validated staged
core-upgrade bundle, identical native dispatch profile, exact old table set plus
the four known new tables (job identity, event history, schedules, occurrences),
zero rows in every added table and exact known physical schema digests on both
sides. The surrounding recovery still refuses resumed traffic, unknown effects,
external credentials, active lanes and changed occurrence history; it verifies
the checkpoint, reconciles current human authority and requires separate resume.
Do not accept arbitrary intermediate releases, numeric ranges, missing tables,
populated additions or arbitrary schema changes.

The first guard refusal remains evidence. Reinspect the same failed operation
under the corrected independent host SDK and restore it once; do not replay the
fault or reset the database. Native execution/checkpoint/source hashes remain
those of the actual core45 attempt. The final foundation becomes core46 so its
packaged SDK contains the corrected recovery implementation; requalify build,
reproduction and kit inputs rather than refreshing an old image's source claim.
Application handlers, available policy, plugin artifacts, public contracts and
runtime dependencies remain unchanged. Qualify the final forward operations on
both sites and retain exact proof of the core45-to46 source delta.
