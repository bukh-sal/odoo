# ADR 0005: additive workspace administrator API

Status: accepted; contract major1 revision3. Trigger: G3 implements the already specified administrator membership/configuration role, which needs strict public request/response schemas before exposing controls.

Add workspace-membership and workspace-settings schemas/examples and fixed routes under `/api/v1/workspace/`. Existing DTOs, permissions, bindings, plan hashes and ordinary read/editor behavior do not change. These are compatible new endpoints, not a wider role or an installer authority. G2 digest/contract checks requalify the additive inventory before the G3 runtime feature is qualified.

Each operation requires a currently authenticated human who is administrator of the explicit X-MP-Workspace. Membership mutations resolve an existing operator-provisioned principal UUID, never accept a backing-user/database/workspace override or create credentials, and affect only that workspace. Removing membership revokes its row; no user account or business data is deleted. Reject removal/demotion of the last active human administrator. Serialize policy changes on the workspace row and use live membership checks; native whole-request serialization retries remain intact.

Configuration writes accept only name, supported default locale and a valid IANA timezone. Slug, public identity, site, installation, grants and deployment settings are immutable/unavailable through this API. The narrow internal ORM elevation targets only the previously authorized metadata row and is explicitly audited. Ordinary legacy metadata CRUD retains its existing ACLs; no site-wide administrative group is granted.

GET returns only the authorized workspace's members/configuration. POST returns a minimal changed target/result; it does not return an administrator-only directory after an actor demotes itself. Account provisioning remains a local operator action with no invitations/email. Application and denial audit records contain actor/workspace/decision/server request ID and validated routing targets, never note text, passwords or bearer tokens. These app audit rows do not replace the independent G5 executor journal/approval store.

G3 qualification must prove viewer/editor denial, permitted administrator changes, cross-workspace rejection, last-administrator protection and inability to mutate installation/execution state. G1 behavior is unchanged. All schema/type/example digests and compatibility tests are updated; existing consumers require no migration.
