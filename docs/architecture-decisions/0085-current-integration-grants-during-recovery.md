# ADR 0085: Current integration grants during native recovery

Status: proposed, 13 November 2026. Implementation and installed qualification
are pending; this decision does not claim a completed repair.

PP-02 document/task integration exposed an omission in the host recovery
authority overlay. The actual existing SQL producer, executed on isolated
temporary PostgreSQL tables and rolled back, retained a newer human membership
revocation but left a checkpoint-approved integration grant approved. Current
grant metadata was absent from the observed authority snapshot. No live
authority, business data or native restore was changed by that probe.

Integration grants belong to platform authority. They differ from application
business ACL rows whose checkpoint semantics remain documented in AP-LIM-015.
Customer Work and Task files both depend on current integration decisions; an
application-specific recovery hook would put this policy in the wrong owner.

The proposed generic host correction observes and binds current grant metadata
by stable installation/plugin/workspace/capability identities. A restored grant
already in the checkpoint takes the current matching decision; a checkpoint-only
grant becomes revoked. New source-only grants are not created in historical
data. The checkpoint grant keyset and history remain intact. Missing or malformed
authority evidence refuses recovery; it never means an empty approved set.

The private restore review must bind this evidence and a protected reconciliation
receipt must prove the expected restored rows. Native authentication, current
membership, image/inventory, effects, checkpoint, fresh-target and independent
approval checks remain. Continuation must preserve the known no-replay boundary.
Resume must require reconciliation proof and bind fresh current-target grants,
including revocations after restoration, before opening traffic.

This adds no browser protocol, manifest permission, application ACL registry or
sandbox claim. Historical images and receipts are immutable. New source tests and
a real populated coordinated recovery are required before acceptance. Older
partial recovery without the new proof must stay closed rather than be silently
relabelled as reconciled.
