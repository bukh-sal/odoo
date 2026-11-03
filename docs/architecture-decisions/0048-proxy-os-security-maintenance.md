# ADR0048: pinned proxy-only OS security maintenance

Date: 2026-11-04 (Asia/Riyadh). Status: accepted for candidate staging;
actual image and ingress qualification required before release selection.

G7's actual nginx image is the pinned official nginx1.30.6 Alpine3.24.3
image. Primary Alpine security fixes identify three older installed origins:
brotli1.2.0-r1, curl8.22.0-r0 and expat2.9.0-r0. Their published fixes are
1.2.1-r0,8.23.0-r0 and2.10.0-r0 respectively. The current official image
contains these old libraries even though nginx itself is current. See
`docs/evidence/G7/20261104-support-images-01/` for exact identities and vendor
snapshots. Treat the installed-library findings as maintenance work, without
claiming every library is reachable through the supported proxy configuration.

Keep the exact official image as base. Fetch the four exact binary package pins
(`brotli-libs`, `curl`, `libcurl`, `libexpat`) and their recursive APK dependency
closure in an isolated, clearly named disposable collector. No application,
database, operator or issuer mounts. Record every APK hash and package identity.
Build one candidate with only this retained package set, no build-time network
and normal APK signature/dependency verification. Do not use allow-untrusted or
mutable package resolution during the offline build. Preserve base source and
license notices and retained APK inputs for reproducibility/release kit.

Review the entire before/after package solution. Require only the intended
origin changes (and explicitly reviewed dependencies if unavoidable), unchanged
nginx binary/version/default entrypoint, complete fixed-version comparison and
absence of credentials/configuration from inputs/layers. Then qualify config
parsing and actual HTTP/native/asset/WebSocket/security behavior against the
existing fresh qualification realm before adopting the candidate. Do not
replace the original working edge or erase current/checkpoint images.

This changes proxy distribution packaging only: no public contracts, SDK/core
version, application/worker image, keys, endpoint/publication authority or native
database migration. G2 remains unchanged. SEC02/04/OPS03 and final release
qualification remain pending until actual evidence covers the selected image.
No final-security, generic sandbox or zero-vulnerability claim is implied.
