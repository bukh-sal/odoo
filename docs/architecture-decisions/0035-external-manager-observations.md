# ADR 0035: external metadata manager and observed health

Date: 2026-11-02. Status: source implementation and G2 revision14 qualification.
Parent: F-01d; specification14.6 and20.1–20.3.

Use the existing operations manager and frozen nomination/request/plan protocols
for external metadata install/upgrade/enable/suspend/unregister. Select runtime
from the exact curated package or published installation, never browser fields.
Registration defaults explicitly to suspended because the nomination has no
activation field; a separate reviewed enable rechecks approval, keys and health.
Upgrade targets every retained site scope; unregister is site-wide and requires
independent endpoint revocation. Required consumers are rejected unless already
handled through a supported separate operation; no implicit consumer mutation.
Native staged installation/removal/uninstall paths remain distinct. The app's
endpoint/health mirror is advisory: the existing OS validator reconstructs plans
with fresh protected authority. No app approval, Docker authority or orchestration
is introduced. Current-image CLI accepts an explicit optional --operator-store;
its existing --store continues to mean the artifact catalog.

The checkpointed metadata lifecycle replaces host application workers. Correct
restart display to say so; the independent external process is never restarted
by the installer. Existing presentation, Odoo interactions, standard native CRUD
and optional custom pages are retained; Canvas is unchanged.

Manager health previously allowed only unknown/degraded because native registry
presence was the only available observation. Revision14 adds healthy **only for
an installed external-service row with installed metadata/database state**.
It requires a published observation whose endpoint site/workspace/installation,
enabled state and expected immutable image match the manifest and scoped health
record. Availability is displayed separately; a healthy process can have a
suspended feature. Missing observation remains unknown; mismatch/outage/revocation
is degraded. Native registry presence still cannot claim healthy. Required native
consumers evaluate an external provider's scoped approval/health instead of
requiring a fictitious native addon. These are cached observations, not executor
authorization or proof of hostile-code isolation.

This is a coordinated compatible major1 revision, not a silent widening: freeze
the revised schema/boundary test and a new external observation example; preserve
all old fixtures, canonical plan hash, request fields and other contracts. Strict
older validators cannot consume the new healthy value and must use revision14
with the accompanying core/shell release. Existing release headers/refresh fencing
prevent old browser code consuming the new release; no claim of mixed strict
validator interoperability. No external plugin SDK shape or token changes.

Qualification requires current schema/old golden/unknown-authority/native-negative
checks, manager routing/reconstruction/scopes/health and legacy native regressions,
then actual coherent versioned core/shell activation and HTTP/browser lifecycle.
Source checks cannot pass SVC04/05, external recovery or the whole G6 gate.
