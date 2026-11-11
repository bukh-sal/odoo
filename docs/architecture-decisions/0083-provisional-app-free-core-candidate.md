# ADR0083: Provisional app-free core candidate

Date: 11 November 2026. Status: accepted for local candidate qualification.

The owner selected the demonstrated eight-addon default: `base`, `web`,
`base_setup`, `auth_password_policy`, `bus`, `mp_compat`, `mp_identity`, and
`mp_core`. Applications and the reference shell remain optional compositions.
The default distribution and candidate-build tools select the clean
`deploy/distribution-r1-core.json` policy. Explicit historical foundation and
probe policies retain their identities and contents.

Version 0.2.1 is a provisional local candidate, supported only for the exact
core/application combinations qualified in the evidence. This does not promise
compatibility with arbitrary addons, third-party Odoo releases, a stable ABI,
long-term support, or production readiness. Broader policy remains deferred.

Existing core/vendor license and attribution files remain unchanged. The
independent Partners test package retains its LGPL-3.0-only label; independent
applications remain private. This decision does not publish, relicense, or
authorize production deployment of any artifact.

The runtime remains independently owned. The eight-addon selection follows
demonstrated behavior and dependency closure, rather than historical folder or
upstream compatibility boundaries. See [candidate support](../candidate-support.md)
and the [supported native surface](../native-application-surface.md).
