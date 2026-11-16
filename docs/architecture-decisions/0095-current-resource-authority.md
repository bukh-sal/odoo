# ADR0095: Current resource authority belongs to the framework

Date: 16 November 2026. Status: accepted for local implementation and qualification.

Apps need record-specific access as well as workspace membership. A checkpoint
must not resurrect a subsequently revoked share. Current recovery reconciles
framework authority but cannot safely discover arbitrary app ACL tables.

Add two domain-neutral, non-RPC framework models: resource policies and principal
capability grants. A policy binds one declared native app model/resource UUID to
its installation, workspace and owner. Capabilities are declared by that app;
labels such as viewer/commenter/editor remain app-owned. No application content,
permission names, editor, navigation or default resource policy enters core.

Trusted native helpers derive current scope, intersect workspace/technical action
ceilings and current installation/feature availability, and enforce reads in both
queries and direct/cached field access. Content writes and policy CAS mutations
lock the same policy row. Policies and grants cannot be authored through ordinary
native RPC. This is an application enforcement facility, not a Python sandbox.

Recovery observes fixed generic tables with public identities, never dynamic app
SQL or imported app code. It reconciles the checkpoint resource footprint with
current authority: immutable identities must match, current revisions cannot move
backwards, missing authority becomes revoked, and current grant tombstones are
retained. New current grants may apply only to an existing checkpoint resource;
no post-checkpoint content is fabricated. A missing referenced identity or final
digest mismatch keeps traffic closed. Both tables absent on a verified pre-feature
core is distinct from partial schema or absence on a feature-capable core.

Existing sealed decisions and pre-feature authority digests remain historical.
New decisions/proofs explicitly bind resource authority when present. Continuation
and resume validate that same proof; they do not replay dump/auth overlays.

The first real private Pages app supplies the populated native consumer and
revoke/write/restore proof. Source tests alone do not qualify installed sharing.
See meridian-phase3-plan.md for this prerequisite and the full useful-app gate.
