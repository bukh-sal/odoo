# ADR0090: reviewed authenticated document metadata

Status: accepted for bounded provisional local qualification,15November2026.

The installed authenticated core25 page has no html language/direction metadata,
and its inherited viewport declaration disables user scaling. Arabic is already
an active native locale. Shared/native interfaces need the actual actor's language
and unrestricted scaling, rather than a forced CSS direction or zoom substitute.

Set only the web.webclient_bootstrap html_data from the existing validated server
session user-context language and native cached res.lang direction; preserve other
attributes and use BCP47 separators. Remove its user-scalable=no. All executable
bootstrap scripts, route/auth/session/CSRF/cache behavior, asset branches and other
QWeb templates remain byte-identical. This does not create an arbitrary language,
URL, renderer or application hook.

Following ADR0089's existing source-attestation pattern, versioned core maintenance
admits only the exact before/after full-file hash pair for this one reviewed XML
file. It does not admit general web/views, Python, models/controllers, other XML,
unknown/removal hashes, static deploy or plugin upgrades. Complete source/image
pins, increasing native versions, independent reconstruction, stored exact approval
and trust/destructive acknowledgments/checkpoint/native maintenance stay required.
Do not claim general owned-web backend maintenance from this pair; future changes
to that surface need a fresh review, or a separately reviewed broader policy.

No wire/schema/permission/freeze change. Source26 is a new immutable identity with
unchanged private apps. Installed HTML, ordinary Arabic preference/RTL and restored
English, available real zoom/motion controls and exact data/authority retention
must be qualified. Source tests cannot establish an installed or visual pass.
