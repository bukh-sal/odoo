# Contract freeze v1

Status: **passed G2**, 28 October 2026. Contract major1, revision4 (ADRs0004/0005/0006). Prerequisite: qualified G1 at commit `73d8ebd2`, with real native/PostgreSQL/browser evidence. Runtime feature acceptance remains at G3-G7.

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
