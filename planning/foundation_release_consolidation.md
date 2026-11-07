# Consolidated foundation qualification

Authorized 7 November 2026. This follows the completed R1, stock WebClient,
shared-foundation rehearsal and BG/BX work; it does not reopen those goals.
Current state and evidence live in `docs/implementation-status.md`.

Deliver one local, reproducible foundation release with the stock Odoo UI,
current SDK/core and background execution. Qualify two independent populated
deployments with different installed applications: Aurora Tasks and Maintenance.
The same available-addon policy and exact release image serve both. Preserve
native list/form actions, app permissions, data and background authority through
maintenance and fresh checkpoint recovery. The peer must remain useful while
the nominated deployment is closed and restored.

## Sequence and exit checks

One item is active at a time. Gates count only after their evidence passes;
documentation and generated artifacts alone earn no progress. Weights total100.
The twelve CF checks are separate from the original99 R1 acceptance checks.

| Gate | Weight | Prerequisite | Exit checks and original requirement mapping |
| --- | --- | --- | --- |
| CF-01 feasibility/freeze | 10 | Completed BX-05 | CF-A: inspect release inputs and freeze a common available-addon policy with separate installed app sets. CF-B: prove a same-policy pre-history core30 baseline can boot and be observed by the current operator; preserve upgrade guards and frozen public contracts. BOOT-01/04, FREEZE; spec §§5.5,6,10,25. |
| CF-02 release inputs | 20 | CF-01 | CF-C: current common image builds and independently reproduces declared inventory without RUN network/cache. CF-D: exact source, curated archives, notices and offline operator/toolchain inputs form a verified local kit without site state/secrets. BOOT-02, PKG, OPS-03; §§19,24,27,28. |
| CF-03 clean application deployments | 20 | CF-02 image | CF-E: fresh Aurora and Maintenance targets from declared release inputs have different installed apps and exact common available inventory. CF-F: populated stock workflows and positive/negative app/workspace permissions pass, with filestore witnesses. BOOT-01/04, ID, TEN, ORM; §§7,8,10,23. |
| CF-04 shared migration/recovery | 35 | CF-03 | CF-G: same supported core transition on both populated deployments preserves app/authority invariants and introduces real history/recurrence schema. CF-H: fault after publication leaves Aurora closed and independently inspectable. CF-I: restore Aurora to fresh DB/filestore, verify checkpoint invariants while closed, separately review/resume, then retry forward. CF-J: Maintenance remains operational with unchanged configuration/data throughout peer recovery. MIG-01/02, LIFE, JOB, OPS-01/02; §§10,12.3,13,19. |
| CF-05 final qualification/retirement | 15 | CF-04 | CF-K: current background roles complete scoped urgent/bulk work, refuse stale authority after release/recovery; affected host/contract/native HTTP and stock UI smoke checks pass. CF-L: clean kit/operator rehearsal, evidence/privacy/provenance review, bounded limitations and exact owned Docker retirement recorded; no uncertain operation. JOB, SVC, SEC, OPS; §§23,24,27,28. |

Freeze before substantial build/test work. First attempt baseline composition
from the recorded core30 source (`334fc9b6a3d27735c20ebaae45ad2a666aea0b44`)
for `mp_core`, SDK and contracts, with current unchanged application artifacts
and the common distribution policy. This is a newly built compatibility test
baseline, not a claim that historical stock-r1 already contained these addons.
The current operator must independently accept its observed schema. If boot,
import or planning fails, capture exact failure and choose the smallest supported
bridge; never rewrite live module versions or relax inventory/schema guards to
force a pass. Limit a failed hypothesis to two materially different attempts
before recording the gap and changing the approach, per spec §25.

## Frozen boundaries

Use stock WebClient and current presentation; no theme/shell rewrite. Aurora
remains the synthetic list-bound task slice pinned to bedrock-2.2 source
`e48e04ed4cf155a83e66e08dfb33a669ebb5c228`. Maintenance is the retained native
community addon with required import dependencies. Notes remains a real scoped
lifecycle target, not fabricated plugin metadata. Background reference jobs are
test workloads, not an expanded task product. Native/same-origin code is trusted.

No public SDK/contract changes are planned. Available packages are not installed
automatically. Keep exact-policy core-upgrade and independent executor approval
requirements. App package changes use their own reviewed lifecycle operation.
Prove actual existing history/recurrence migration rather than inventing a
business field solely to manufacture a schema change.

The local kit must retain source/license notices and reconstruct operator state
from declared inputs. It must not copy author catalogs, approval journals,
credentials, application databases/filestores or issuer keys. Reuse unchanged
large transport inputs where possible; keep raw logs/private fixtures out of Git.

Optional and excluded: extra Aurora features/importing user data, automated
autoscaling, provider delivery, broker/fan-out/workflow engines, breaking platform
major upgrade, plugin-free deployment, hostile-code isolation/R2, marketplace/R3,
publication and production deployment. New faults within the required path are
fixed and qualified here; unrelated improvements enter the remaining-checks
register with a trigger. Only a genuine missing user input blocks this goal.
