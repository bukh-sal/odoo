# Provisional app-free core 0.2.1

The default core contains `base`, `web`, `base_setup`, `auth_password_policy`,
`bus`, `mp_compat`, `mp_identity`, and `mp_core`, with the SDK and stock WebClient.
Applications and the reference shell are optional. The default build policy is
[`distribution-r1-core.json`](../deploy/distribution-r1-core.json).

This is a local candidate with support limited to the recorded combinations.
It carries no stable ABI, arbitrary-addon compatibility, production-readiness,
or long-term support promise. Historical sealed releases retain their own exact
source, artifacts and evidence; current changes do not rewrite them.

The independent private Partners 0.1.0 package was qualified unchanged across
core 0.1.53, the useful workspace-navigation successor 0.2.0, and corrected core
0.2.1. Its exact archive digest is
`sha256:98ab90210e81b2bf28e23909eac549b1af637459c356b5680f37c2314002e2bd`.
Qualification covers useful scoped records, native forms and revision checks,
actual event delivery, normal install/uninstall/source removal/reinstallation,
and populated checkpoint recovery with current authority and separate resume.
It does not establish compatibility for other archives within a declared range.
The initial 0.2.0 reinstallation exposed retained-idempotency receipt reuse;
0.2.1 fences recreated bindings with the release epoch. The original failure
remains evidence, and 0.2.0 is not the final lifecycle candidate.

The supported development subset and limits are documented in
[native application surface](native-application-surface.md). Complex migrations,
browser event callbacks, arbitrary external worker implementations, and varied
independent applications have not been newly qualified by this candidate.
Tasks, Storage and Documents remain later work.

Core/vendor licenses and notices are retained unchanged. The Partners test
package retains its LGPL-3.0-only label and remains private, as do other
independent application sources. No publication, paid services or production
deployment is authorized by candidate qualification.

See [ADR0083](architecture-decisions/0083-provisional-app-free-core-candidate.md)
for the owner's selection and policy disposition.
