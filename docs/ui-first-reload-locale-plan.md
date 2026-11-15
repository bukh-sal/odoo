# Correct native assets on the first locale reload

Activated15November2026 after core26/config25 actual preference roundtrip, before
source changes. Keep the original UI goal/full cards, Meridian reference and all
eleven protected sites. Arabic is active; English and every profile/authority/
business/history baseline are restored. Sample82 remains revision4.

The actual authenticated document gets the new language/direction immediately,
but assets lag one locale: Arabic html/bodyrtl/ltr with LTRasset, then English
html/bodyltr/rtl with RTLasset. Another normal English reload selects LTRagain.
Screenshots and stylesheet URLs are preserved in .local/ui-document026-01/browser.

Source trace: session_info refreshes request.session.context from the current
user, while QWeb _get_asset_links reads its current environment language. The
rendering context must synchronize only validated user_context.lang onto the
request environment before request.render chooses bundles. Preserve every other
context key, session/actor/workspace/authority/CSRF/cache/menu/appearance behavior.
No URL language input, client-side second theme/direction engine or forced CSS.

First add a differential using the actual rendering-context method and actual
native asset selection method with fake external environment/cache boundaries:
old source chooses the preceding direction, fixed source chooses the new one,
both directions; unchanged/missing context stays bounded. Preserve returned
session_info identity and all unrelated context. Do not replace this producer/
consumer witness with only an update_context spy.

Use ADR0089's exact reviewed reader source-pair pattern for old current ir_http
reader to new reader, keeping its historical pair and ADR0090bootstrap pair.
Unknown/removed/other backend, unversioned/static/plugin routes and forged exact
review still refuse through real core planner/independent reconstruction. New
ADR documents this narrow presentation context change; no broad backend policy.

Reserve next unpublished core0.2.27/web19.0.2.27.0/mp_core19.0.0.2.27 after checking.
Expected five shipped deltas: ir_http reader, staging SDK reader and identities.
All five apps/Python/metadata26 XML exact. Affected tests/freeze, one immutable
clean image/layer audit, ordinary10scope core review/ack/checkpoint/apply, fresh
observer and exact18tables/fullhistory/10sites.

Installed ordinary preferences must load correct language/HTML/body/stylesheet
on the FIRST reload in both directions. Then whole customer/task/pinned-current
Documents/native table and dialog RTL desktop/narrow/lightdark with real Arabic
and mixed identifiers. Collect related layout findings before a coherent fix;
restore original language/theme/viewport and all semantic profiles. No required
extra refresh or translation-completeness claim. Finish the original true zoom,
motion/contrast/current authority/optional-app/current appfree/final canonical.
