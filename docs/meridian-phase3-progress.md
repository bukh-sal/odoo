# Phase3 implementation checkpoint

16 November 2026. Full Meridian goal remains active; milestones1/5. Phase2's
visual gates remain open. Core57 is installed on empty18741/config4; the populated
Partners review remains core56/config18. Pages is not yet installed or authored.

## P3.0 source implementation

[ADR0095](architecture-decisions/0095-current-resource-authority.md) records the
framework/app boundary. The core57 source checkpoint below was subsequently
packaged and installed on the empty cohort. It is not a populated sharing/recovery
qualification. The web module remains56 because its bytes did not change.

- New private `mp.resource.policy` and `mp.resource.grant` models contain generic
  authority metadata only. Ordinary native CRUD and cached field access refuse.
- `mp.resource.scoped` and private helpers enforce declared model/capability,
  current actor/workspace/installation/feature and existing application/technical
  ceilings. Query predicates run inside native search, before offset/limit/count;
  existing field/read-window hooks enforce direct/cached reads. No user SQL,
  fabricated scope, privileged ORM environment or application ID is introduced.
- Content mutations take a shared workspace lock and the same policy row lock
  as sharing CAS. Grant replacement retains tombstones. Current eligible service
  principals are not artificially excluded, but grants create no credentials and
  never widen a credential's actions. Pages can offer human sharing in its UI.
- Recovery reads fixed generic tables in the same readonly snapshot as native
  authority/authentication. Psql selects an absent-table alternative before SQL
  parsing. A partial schema, or absent tables on core57+, refuses.
- The existing checkpoint/authority proof now conditionally binds resource
  policies/grants. It preserves current revocations/defaults and grant tombstones
  over the checkpoint's content footprint. Current grants for retained resources
  can be restored; post-checkpoint resources/content are never fabricated.
  Stable identity/owner must match and policy revisions cannot move backwards.
  Changes at the same revision refuse. Completion and resume bind the proof;
  continuation source hashes include both new recovery and native-auth readers.
- Legacy pre-feature canonical authority/proof shape is unchanged. No old
  prepared review, checkpoint, dump, filestore or authentication overlay was
  rewritten/replayed.

## Evidence and limits

| Evidence | Result and scope |
| --- | --- |
| New helper/mixin tests |12 pass using actual current-scope resolver, WorkspaceScoped/core installation guards, native SQL wrapper, capability ceiling and new helper/mixin with fake native/SQL boundaries. Covers scope/feature/install/foreign/technical/forged carrier denial, current service credentials, query predicate placement, cached/direct reads, locks, CAS, subject/capability refusal and private authority models. Not an installed ORM/concurrency claim. |
| New resource recovery tests |14 pass: exact schema, identity/monotonic state, missing grants, new shares only for checkpoint resources, old schema, proof/source/resume bindings, fail-closed completion before registry/dispatch, fixed overlay and actual observer boundary. |
| Existing affected tests | Grant9, native-auth11, restore-dispatch19, continuation7, restored-release9, recovery8, optional-reference14, binary14, native-versions7 pass. |
| Clean packaging regression | Materialization6 and candidate build-boundary15 pass. Eight-addon/owned file closure and existing build route remain; no actual57 image/all-layer claim. |
| Contract freeze |122files/11rows pass; no wire/freeze revision. |
| Actual readonly old-core SQL | Empty18741/core56 observed4principals/6members/8native users; verified absent resource schema strips only the new observation wrapper. Target hash remains ef722b4f. Receipt `.local/meridian-phase3-old-authority057-01/result.json`. No DB write or restore. |

The bounded affected set totals145 passing tests; no full-host run. Receipts are
under `.local/meridian-phase3-source057-{01,02,03,04}/`;04 holds the final12 helper
checks after the private-field and current-service-credential cases. Initial helper harness lacked
a contextmanager and two native boundary shapes; those test-only setup errors
were corrected. The first isolated restore-dispatch invocation lacked the optional
tools import path; its failed receipt is retained. Corrected isolated imports
then passed. Its SQL fixture now supplies the actual explicit pre-feature schema
producer shape; no assertion was waived.

No Docker resource mutation, image build, apply, restore, application source edit,
dependency download, UI preference change or cleanup occurred in this checkpoint.
Populated18740/config18 and empty18741/config3 remain on core56. Reference39/48
remain visible; human38 is protected.

## Installed empty-core57 checkpoint

ONE clean build from ffae0af867569e0460d3d050cb1421a45c0ed08d completed in31.938s.
Image `sha256:d250951285e5b3c76a89c13068027348df712be81f77db2b69624e11a41de541`,
record be464864a54e,4031curated source inputs,14final layers/3750project files.
Runtime/all-layer audit verifies eight addons, zero application archives and
exactly the intended11file changes from empty56. No dependency/runtime relabel.
Receipt `.local/meridian-phase3-build-empty057-01/complete.json`.

Normal stage/plan/register/review/exact-hash approval/apply completed ONCE
for operation5da135fe-0263-49e3-bdff-f186714431e4, plan
`sha256:9c8235112790a645a6b364cb302eecdb9a3e8f3f3dd88795807775632befe54f`.
The only native change is mp_core56→57, migrations[], zero plugin targets,
retained checkpoint, no permission/trust metadata changes. Required native trust
and destructive acknowledgments followed normal policy. Apply143.812s/exit0.
Empty target is config4, SHA843e7e2b1b95; old image/worker/checkpoint are retained.

Actual native installation created both authority tables. Fresh production
authority observation returns schema_version1/policies[]/grants[]; direct counts
are0/0. The original nine tables are row/value-exact to baseline, including zero
app installations/features/grants/bindings/jobs/events and4principals/6members/
2workspaces. Browser40 reload shows the honest no-app home. This is an installed
schema/empty authority proof, not a per-record permission or concurrency proof.

`.local/meridian-phase3-final057-01/result.json` reobserves both cohorts after the
browser reload: populated18contacts/21events and all10tables exact; empty all9
tables exact; all protected target hashes/five private heads/4031source inputs
exact. Populated config18/imageb7eb5967 remains unchanged. No business write,
restore/replay, app admission, publication or cleanup. All new operations are
terminal; never rerun the old wrappers.

The user's100% zoom reply then enabled fresh matched directory/Acme record
captures on the populated56 cohort against Meridian. Native zoom1/scale1 and
1440x900/DPR1 are verified; actual font aliases share the same Geist Latin bytes.
See phase2 review and `.local/meridian-phase2-pair100-057-01/`. Complete CDP
originals replace a retained preview-clipped setup attempt, without image resizing.
The final057-02 readonly receipt confirms both cohorts' rows/targets/source pins
still exact after these read-only interactions. Native200% is now separately
requested; no response/acceptance assumed. Pages remains the active code item.

## Next action and remaining acceptance

Create the real thin private Pages consumer against the installed57 capability;
do not repeat the completed build/transition. Preserve both review cohorts.
Use Pages for native query,
relation/title, cache, two-writer/revoke ordering and checkpoint/restore proofs.
Fake SQL boundaries do not establish any of those installed claims.

P3.0 is not accepted until those installed proofs pass. Sharing/recovery remains
unaccepted until the real post-checkpoint revoke survives supported restore.
Pages authoring/editor/Home/tree, durable collaboration/history, installed visual
comparison, phases4/5 and phase2's native zoom/consumer breadth are still required.
