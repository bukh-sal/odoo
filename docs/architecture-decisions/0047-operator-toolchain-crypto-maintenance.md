# ADR0047: compatible isolated operator cryptography maintenance

Date:2026-11-04 (Asia/Riyadh). Status: accepted; source/toolchain qualification
required before the compatible G2 revision is marked passed.

G7 current public advisory lookup finds matches for cryptography42.0.8 in the
isolated Windows operator environment. The actual app/worker already use50.0.2
and have no matching Python-package records in the retained point-in-time query.
The current operator tooling input/lock are explicitly covered by G2revision16.

Pin the operator tooling input to cryptography50.0.2 and re-solve its hash lock
with the existing trusted compiler, preserving all unrelated package versions.
Use binary wheels and the project-owned .venv only; no global Python change,
source metadata build hooks, runtime image rebuild or endpoint/key rotation.

This is a compatible toolchain revision. Public schemas/examples, canonical
approval bytes, scope/key/issuer rules, RSA/RS256 protocol and application/worker
source remain unchanged. Requalify frozen contracts plus the operator's token,
key provisioning/publication, approval/reconstruction/expiry and core-maintenance
consumers on actual Windows cryptography50. Retain old lock and query evidence.
Only the reviewed tooling files and this ADR enter the new freeze revision;
every prior schema/example and unaffected frozen source hash must stay exact.

Do not turn a successful package upgrade into final security qualification.
Bundled native crypto libraries and current host tooling metadata/advisories must
be recorded. Debian source-package/vendored/PG/nginx findings, including the
published Cyrus SASL fix, require their separate substrate/reachability review.
The app/worker's independently approved image/authority and current data stay
unchanged by this local operator dependency maintenance.
