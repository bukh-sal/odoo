# R1 network independence

The current managed reference boots and runs its reference backend on internal
app/database/worker networks. The browser-facing Nginx edge alone also joins
the named ingress bridge. [Current topology and TCP controls](evidence/G7/20261104-network-independence-01/runtime-network-boundary.json)
verify that the app has no IPv4 default route, reaches its internal database,
and cannot connect to the public TCP control. No application bytes were sent
to that control. The selected proxy forwards to the local app; it is not an
arbitrary forward proxy. This is an application egress boundary, not a claim
about Docker/host DNS, browser background services or arbitrary native code.

Actual fresh boot, native/reference installation and original-actor worker job
are retained at the same immutable image and internal topology. The production
asset shell, native Notes list, minimal Canvas and Settings have also run with
foreign page-origin HTTP requests intercepted and refused. A reserved-domain
control proved interception worked; no app-originated foreign HTTP or WebSocket
destination was observed during those recorded flows. Native form/Labels,
two-tab isolation and accessibility/RTL flows still need their final current
browser coverage. No full OPS03/G7 completion follows from this backend review.

[The current source classification](evidence/G7/20261104-network-independence-01/reviewed-product-ties.json)
binds all4,159immutable inventory file hashes and reviews24source families,
486translation files and16test files containing Odoo/OpenERP host references.
The initial broad candidate scan matched identifiers such as `odoo.Command`
and `odoo.netsvc`; corrected host boundaries explicitly exclude11false-positive
matches. No required Odoo-hosted runtime service was found in this finite scope.

| Retained tie | Classification and R1 decision |
| --- | --- |
| Account OAuth URL and stock account menu | Optional integration. Platform root omits stock UserMenu. The retained authenticated route constructs a URL; it makes no server-side account call. Explicit use could disclose database UUID/name/base URL; reference workflows do not invoke it. |
| Support/buy metadata | Optional user-facing link. Inherited session support URL remains metadata; it is not needed to load local views or run plugins. |
| Apps/Themes catalog and Enterprise upgrade dialog | Optional commercial integration. Platform navigation, Settings and curated local catalog/lifecycle do not host these stock purchase flows. The stock dialog's external video is also optional. No Enterprise code is installed. |
| Login Powered by Odoo, local logo, Community/LGPL/vendor text, release author metadata | Branding/attribution. Preserve inherited source and required notices. App appearance is custom; provenance remains explicit. External anchors require user navigation; the logo is served locally. |
| Documentation/2FA Learn More/PWA vendor links | Optional user-facing links or attribution. Local TOTP, native views and custom pages require no remote document/PWA account service. |
| Database manager privacy notice | Retained upstream content; public database-manager routes denied and list_db=False. Independent bootstrap uses no stock database manager. |
| Publisher-warranty URL default | Inactive update configuration. Full retained Python/XML/JS mention scan finds the parser declaration plus five config-manager test fixtures, with no active consumer. Actual max_cron_threads=0. No automatic warranty/update client found in the retained scope. |
| Mail test address and website placeholders | Optional configured SMTP test/examples. Reference apps configure/send no mail. Do not treat an example address as telemetry. |
| Translation/test/docstring URLs | Inherited content or developer examples. Preserve notices and test source; do not infer arbitrary translated HTML or arbitrary tests are network independent. |

The broader branded-host review also identifies `fonts.odoocdn.com` in the
optional `web.report_assets_common` bundle. This is an automatic font request
when those report styles and covered Unicode glyphs are used; it is not merely
an anchor. Actual asset-manifest inspection confines that font file to the
report bundle. The two production CSS assets observed on the reference app
contain no Odoo CDN font URLs. R1 reference screens do not expose a report
feature. Any future report integration must substitute local fonts or establish
an explicit external policy and requalify. Preserve the inherited font source
and its notices. Other broader-host matches are a symbolic test URL and an
inherited translation link containing `odoo` in its host; ownership of that
third-party-looking domain is not asserted or required.

The selected addon inventory excludes IAP, IAP mail, Unsplash, external module
installer and Enterprise implementations. Keeping stock source links does not
install their referenced ERP/commercial modules. Existing Odoo ORM, native
views, actions, dialogs, notifications and command infrastructure remain reused.
No source stripping, frontend rewrite or Canvas product expansion was needed.

Build-time source/package/toolchain/provenance downloads are separately pinned
network uses. Optional user-followed links, explicit SMTP/account/PWA/upsell use,
operator acquisition, future plugins and OS/browser/Docker services are outside
the reference application's offline claim. Revisit the classification and actual
blocked-origin tests when addon policy, assets, navigation, optional integrations,
network topology or upstream version changes. Commercial licensing/distribution
decisions remain outside this local qualification.
