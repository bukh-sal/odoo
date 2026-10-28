# Contract freeze v1

Status: **passed G2 revision8**,28 October2026. Contract major1; compatible deployment enum extension under ADR0015. Prerequisite: qualified G1 at commit `73d8ebd2`, with real native/PostgreSQL/browser evidence. Runtime feature acceptance remains at G3-G7.

Normative semantics: [protocol-v1.md](protocol-v1.md), [ADR0003](../architecture-decisions/0003-r1-contracts.md). Machine inventory [freeze-v1.json](freeze-v1.json) contains exact SHA256 for every schema/type/example/validator/test/lock and maps owning phase, acceptance IDs and G1 correspondence. It excludes itself and unrelated evidence/status to avoid self-reference. Every path in the table has an exact digest in that inventory.

| Contract | Owning phase | Schema/type/example boundaries |
| --- | --- | --- |
| workspace enforcement | C/G3 | `packages/contracts/v1/workspace-context.schema.json`, `packages/contracts/v1/role-permissions.json`, `packages/contracts/examples/v1/workspace-context.json` |
| actor and plugin identity | C/G3; F/G6 | `packages/contracts/v1/call-context.schema.json`, `packages/contracts/v1/service-request.schema.json`, `packages/contracts/v1/service-response.schema.json` |
| executor approval | E/G5 | `packages/contracts/v1/plan.schema.json`, `packages/contracts/v1/approval.schema.json`, `packages/contracts/examples/v1/plan.canonical.json`, `packages/contracts/examples/v1/plan.sha256`, `packages/contracts/examples/v1/approval.json` |
| versions and migrations | E/G5 | `packages/contracts/v1/manifest.schema.json`, `packages/platform_sdk/modular_platform/contracts.py`, `packages/contracts/examples/v1/manifest-native.json` |
| service bindings | C/G3; D/G4; E/G5 | `packages/contracts/v1/binding.schema.json`, `packages/contracts/examples/v1/binding.json`, `packages/contracts/v1/documents.schema.json` |
| external-service packaging | E/G5; F/G6 | `packages/contracts/examples/v1/manifest-external.json`, `packages/contracts/v1/endpoint.schema.json`, `packages/contracts/v1/worker-claims.schema.json`, `packages/contracts/v1/worker-request.schema.json`, `packages/contracts/v1/worker-response.schema.json`, `packages/platform_sdk/modular_platform/tokens.py`, `packages/contracts/examples/v1/worker-public.pem`, `packages/contracts/examples/v1/worker-token.txt` |
| UI host | C/G3; D/G4 | `packages/contracts/v1/host-context.schema.json`, `packages/contracts/v1/route.schema.json`, `packages/host_sdk/src/index.ts`, `packages/host_sdk/tests/plain_page.ts`, `packages/contracts/examples/v1/host-context.json` |

No-open-critical-decisions checklist:

- [x] Workspace carrier, current actor/backing mapping, role/action matrix, global rules, live authorization, cache keys/invalidation, missing/forged scope and bootstrap routes fixed.
- [x] Human browser attribution versus authenticated technical installation, provider-chain preservation and intersected grants fixed; no generic elevation or human delegation.
- [x] Independent OS CLI/store approval, exact RFC8785 bytes/hash/schema, expiry/revocation/reservation, lock/recovery behavior and golden fixture fixed.
- [x] Numeric X.Y.Z spelling/order, 19.0.X.Y.Z mapping and migration target/phase paths fixed.
- [x] Consumer-local aliases, one-major range subset, exact provider/version/generation and wire errors fixed.
- [x] Metadata-only external artifact, independently operated pinned Compose/endpoint, RS256 issuer/key provisioning/claims/audience/lifetime and lifecycle separation fixed.
- [x] Snake_case host context, framework-neutral mount/update/dispose, URL workspace/routing, stale generations, native adapter and service options fixed.

Validation: `.venv/Scripts/python.exe -m unittest discover -s tests -p test_contracts.py -v` (17 passed); `npm --prefix packages/host_sdk run check` (passed); `.venv/Scripts/python.exe tools/check_contract_freeze.py` (56 files/seven rows passed). Evidence: [`gate-G2.json`](../evidence/G2/20261028T020915524386Z/gate-G2.json). G1 source boundary checked unchanged, rather than repeating passing infrastructure tests.

Tests cover strict metadata/no imports, unknown authority fields/majors, numeric/native ordering and migration paths, explicit parallel service majors/provider selection, metadata-only services, golden plan serialization/hash and independent ECMAScript comparison, approval target/expiry/revocation/consumption semantics, DTO/input boundaries and RS256 vectors. The retired-key token is deliberately expired and its private key was discarded. Synthetic endpoint image digests are fixtures and cannot certify a real deployment.

Change discipline: update an ADR with trigger/semantics/consumers/migration impact; bump public major for breaks or inventory revision for compatible changes; update schemas/types/golden fixtures and consumers; invalidate and requalify affected checks. Do not update hashes alone to conceal drift. Implementation may proceed internally without contract changes. G3 then G4/G5/G6/G7 remain required; G2 is not the goal endpoint.

Revision2 requalified the strict UTC calendar validator and explicit core capability owner; the original freeze evidence is preserved. No golden plan hash, token protocol, DTO shape or role authority changed.

Revision3 adds strict workspace-administrator membership/settings schemas/examples under the existing role/authority rules ([ADR0005](../architecture-decisions/0005-workspace-admin-contract.md));17contract tests,56frozen files/typecheck pass. Runtime admin qualification remains C04.

Revision4 adds concrete composition/board/documents2.0 boundaries before G4 runtime work; see ADR0006 and the machine inventory. Existing1.0 examples remain compatibility fixtures.

Revision5 clarifies initial board discovery without selecting a workspace; ADR0006 addendum, existing explicit-ID request remains compatible.

Revision6 supplies optional custom snapshotDraft recovery, with strict JSON/filename/ownership/size semantics; see ADR0007.

Revision7 adds strict operator preparation/request/context/catalog/status DTOs and examples (ADR0009), with proposed plan ID/hash/targets/trust/restart checks and explicit application-request versus journal-mirror authority. New terminal-newline fixtures confirmed the old `$` end-anchor ambiguity;172 anchored patterns in22 schemas now use the portable absolute-end assertion. Existing valid fixtures and the golden plan hash remain unchanged. Current [G2 revision7 evidence](../evidence/G2/20261028T0630513883922Z/gate-G2.json):74 frozen files,26contract tests plus50affected archive/resolver/plan/CLI tests, TypeScript check. Context/catalog metadata bounds preserve the full512-character manifest metadata. Earlier0628543547965Z candidate retained; final adds the catalog-bound/unsigned-warning check. UI handlers are not yet enabled; strengthened G5/G7 runtime consumer checks remain required. Existing qualifiedG4image/source is unchanged.

Revision8 adds explicit platform-only `deploy` plan/target/artifact action and status display under ADR0015, with `plan-deploy.json`. App request schemas still reject deploy; independent staged CLI/executor only. Plugin version/migration rules and old valid DTOs/golden serialization remain unchanged. Older consumers reject the unknown operation until explicitly upgraded. Source/runtime qualification is required before current revision is passed or applied.

Revision8 source/contracts requalified by `docs/evidence/G2/20261028T150700Z-deploy-revision8/gate-G2.json`:75files/7rows, fullhost150/Linux123 regressions including6new platform-deploy checks. Previous golden hash unchanged; actual deploy/browser acceptance remains G5.

The final revision8 normative prose/inventory addendum is qualified in `docs/evidence/G2/20261028T153300Z-deploy-protocol-addendum/gate-G2.json` (75files,26contract tests, unchanged golden; no executable/schema delta from150/123). Earlier150700Z record is retained as the initial revision checkpoint.


Revision9 adds operator-only `core_upgrade` plan/public-status enum and `plan-core-upgrade.json` under ADR0016. Existing plugin targets/artifacts use `deploy` to retain all package scopes. Native core versions/source/migration hashes are explicit immutable lock/display data; destructive+native-trust acknowledgement and controlled maintenance are required. Static-only deploy and app request enums are unchanged. Old valid DTOs/golden serialization remain compatibility fixtures. G2 and affected consumers require requalification; actual core upgrade/recovery/UI07 remain G5.
