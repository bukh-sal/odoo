# ADR0091: current user locale before native asset selection

Status: accepted for bounded provisional local qualification,15November2026.

Actual core26 preference changes expose a one-request lag. The HTML/new user
context uses the new language, while native QWeb selects assets from the preceding
request environment language. Another reload works, but is not an acceptable
locale-switch interaction. Keep the preserved real roundtrip/source26 evidence.

The native rendering context reads existing session_info once and synchronizes
only its validated user_context.lang through the existing request.update_context
before request.render. Other context keys, trusted scope, user/actor, returned
session_info identity, cookies, appearance, asset/cache/menu/auth/CSRF behavior
remain. There is no browser input, new language/authority selector, forced CSS or
second direction engine. The existing request merge and QWeb asset reader are
unchanged; source tests execute both as the producer/consumer witness.

Extend the existing exact reader-source pair pattern for this one full-file
before/after transition. Preserve ADR0089's historical pair and ADR0090's bootstrap
pair; do not admit unknown hashes, arbitrary web backend/templates, static deploy,
plugin upgrades or unversioned changes. Exact inventories, independent plan
reconstruction/approval, acknowledgments, checkpoint and native maintenance remain.
No wire/schema/freeze change or broad web-backend support claim follows.

Use a legitimate new core27 identity with unchanged applications. Actual ordinary
preference changes must select correct HTML/body/styles on the first reload in
both directions, then complete the original RTL journey and restore English/data.
Source-only tests do not establish installed success or full translation support.
