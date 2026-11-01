# Native staging with retained external metadata

F-01d / G6-REFERENCE-STAGING-01, spec §§6.2, 10, 14.6, 25; ADR0034.

84 current-source checks pass (`qualification.json`), including ten new checks
for exact external-root retention, native/manager upgrade, current-image scope
installation, catalog refresh, core coverage, inert unregister tombstones and
independent staged reconstruction. The other suites cover native staged plans,
core/static deployment, source removal, retained reinstall and plan boundaries.
Frozen contracts remain 94 files/eight rows, unchanged and passing.

Staged planning and manager planning derive external pins exclusively from the
independently observed published release. The native image does not pretend to
contain those metadata packages or a fabricated addon. Current catalog validation
still applies; missing metadata, substituted manifests and external native
targets fail closed. Unchanged exact published artifacts retain their historical
trust evidence while the plan binds fresh catalog validation. Native targets get
the actual current validation for changed artifacts.

Core/static deploy covers every native installation scope; exact external roots
remain unchanged without becoming native targets. The existing native-state,
artifact, permission and trust-change guards remain. Source-removal reconstruction
and sanitized candidate validation also carry retained external roots. Current
image install preserves the exact published artifact identities/trust required by
the independent validator. CLI staged planning now uses the independent external
reader rather than constructing a reader without external observation.

Initial new tests had an inconsistent catalog snapshot and omitted the existing
request schema version; corrected fixtures pass without weakening those gates.
The existing source-removal fixture also paired current reference archives with
the old platform0.1.0 helper default. It now derives platform/core version from its
actual document environment; all21 removal checks pass.

No Docker assets, live database changes, installed deployment, metadata
registration, remote runtime action or SVC acceptance is claimed here. A real
native connector rollout retaining a registered provider is still required.
Changed-worker-image transition/recovery is not qualified by these tests.

Return to F-01d: close the final connector apply authorization gap and queued
native-feature prerequisite, then make the coherent versioned image and run
actual reviewed registration/connector/remote/lifecycle/recovery qualification.
