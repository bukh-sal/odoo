# 0092: Shared interface icons across native asset roots

Status: accepted for local candidate implementation; installed qualification
required. Date:15November2026.

Core0.2.29's installed empty-core check exposed a dependency error on sign-in.
The actual frontend lazy bundle includes the native command palette, which now
uses the shared Icon. Icon/data/template were declared backend-only. Backend
rendering and isolated component tests could pass while frontend modules failed.

Use one `web._assets_interface_icons` native asset group for the pinned SVG data,
Owl Icon, template and base/loading/directional styles. Include it after the
existing Owl module in both actual roots: backend's `_assets_core` and the
independently assembled `assets_frontend`. Do not add another Owl, runtime icon
fetcher, frontend business chrome, sidebars or preferences to the minimal loader.
The public component/data and style declarations stay unchanged; the relocation
is not a new domain or routing API. Retain exact Lucide/Feather attribution.

Owned-web maintenance previously allowed only appended local backend references.
Extend that fence for this exact reviewed relocation, preserving all native
metadata and every other asset declaration/order. The three prior references
must occur once immediately after foundation.css, the new group has four fixed
paths, both includes follow the existing Owl module, and every path has a valid
digest in the independently inspected inventory. No request flag, arbitrary
group edit, external URL, missing source or native-data change is admitted.
Existing backend append checks remain. Normal image/source reconstruction,
separate exact-hash operator approval, checkpoint and recovery remain required.

The regression invokes the actual native ordered include/remove/path consumer
with fake ORM/manifest lookup, and retains the captured029 manifest. It reproduces
the old frontend omission and verifies both current roots without expanding the
minimal bundle. Maintenance negatives cover substitution, extras, duplication,
order, missing/invalid inventory and native declarations; inputs stay unchanged.
Source tests and identical Sass/RTL maps do not establish installed success.

Candidate0.2.30 gets new platform/web/native identities because029 images already
exist. Retain those images and failure evidence; do not relabel/rebuild them as a
successful029 release. Private app bytes remain unchanged. Requalify actual
sign-in and empty-core UI through a normally reviewed upgrade before app
admission. Legacy login branding/account glyphs and the original full UI matrix
remain separate open cohesion work. No wire/freeze/security model changes.
