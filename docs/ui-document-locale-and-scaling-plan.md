# Native document locale and unrestricted user scaling

Activated15November2026 after installed core25/config24, Partners1.6 and actual
native Save/stale qualification, before source edits. Continue the original UI
goal; no new application, UI framework, wire contract or locale policy.

Current preflight .local/ui-current-matrix025-01 proves4086curated inputs match,
all18tables equal the post-Save baseline,10other sites unchanged, Alice6 is
en_US/AsiaKuwait, and ar_001 is already active/rtl. No language installation,
admin login, authority change or source injection is needed. The first private
SQL query wrongly looked for delegated profile fields on res_users; preserve
preflight-before-profile-join.py. Correct source-consistent res_partner join
passed read-only; this was a diagnostic query mistake, not a product failure.

Actual authenticated DOM has no html language/direction attributes. Browser
preflight records DPR1.1/visualViewport.scale1, viewport1363x789, reduced-motion
false. The native QWeb webclient bootstrap also declares user-scalable=no.
These inherited defaults should not become intentional accessibility limits.

## Coherent owned-core correction

Set authenticated webclient html_data language and direction from the existing
validated session user-context locale and native res.lang data. Preserve other
html_data entries; convert locale separators to BCP47 form. Do this in native
server-rendered web.webclient_bootstrap, rather than mutating DOM or inventing a
client registry. Remove only user-scalable=no from its viewport declaration.
Keep layout/auth/session/CSRF/cache/menu/assets/other templates unchanged.
Do not use a browser URL value as a new authority or language source.

Current versioned core maintenance permits web static assets and a separately
reviewed appearance reader, not this non-static QWeb file. Extend that existing
exact reviewed-source pattern for the one actual before/after bootstrap file,
with an ADR and independent-validator counterexamples. Do not broadly admit
web/views, Python, controllers, models, arbitrary template files or unbound
hashes. Retain exact base/target inventories, curated source maps, strictly
monotonic native versions, same package/Python policy and stored approval.
This is an explicit small maintenance capability for owned UI, not a bypass.

Reserve unpublished0.2.26/native19.0.0.2.26/web19.0.2.26.0 after checking current
assignment. Expected five shipped files: bootstrap XML, staging SDK reader and
three identities. All five private app archives stay unchanged. No app/backend
business model, permission, job/authority/schema/freeze change.

## Evidence and normal rollout

Tests must use the actual XML directive/native locale-data producer shape for
en_US/ar_001, preserve unrelated html attributes and reject invented locale
fallbacks. Prove all other template nodes and executable bootstrap script bytes
unchanged. Exercise actual core planner/independent reconstruction with exact
reviewed hashes and refuse stale/forged/foreign backend changes before mutation.
Freeze/affected staging/identity checks; no broad test repeat merely for counts.

One immutable unchanged-app candidate, exact five deltas/all-layer audit, normal
ten-scope core review/acknowledgment/checkpoint/apply/fresh observer and exact
18table/fullhistory/10site retention. Preserve all old operations; never replay.

Then ordinary IAB preferences switches the existing actor to already-active
Arabic, checks server HTML lang/dir, actual RTL assets/directions, mixed labels,
native/custom/dialog/pinned-document journey in desktop/narrow/light/dark, and
restores English through the same native preferences. Do not use forced CSSdir.
Use browser zoom controls only for actual200%zoom; record metrics and do not
substitute viewport/pinch scaling. Test actual reduced-motion preference with
documented controls, restore original state, measure rendered contrast/focus.
If controls cannot expose a required check, record that exact limitation and
continue other independent cards without inventing evidence.

Current Sample82 revision4/one saved clarification is the baseline. All old
revision3 save helpers/intents are historical and must not rerun. Optional-app/
authority/current zero-one-many and final canonical remain original required
work. Native outer/inner framing remains a separate visual critique. No cleanup,
publication, full-translation or formal accessibility claim.
