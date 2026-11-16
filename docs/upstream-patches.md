# Upstream patch ledger

The upstream source checkout and its license/copyright notices are preserved. Platform additions remain separate. The generated R1 distribution includes the narrowly reviewed numeric-parser correction and metadata patch below, each bound to original/resulting hashes in its inventory. No ORM, authentication or registry engine replacement is introduced.

| File | Reason | Rejected alternative | Verification | Merge risk | Removal condition |
| --- | --- | --- | --- | --- | --- |
| Owned palette close button and collection table border (19.0.2.48.0) | Installed47 inspection found an optional undefined close alias and row borders inheriting ink after shorthand reset; use the actual required close callback and preserve border color when removing outer width | Hiding the close control, swallowing its error, runtime CSS injection or accepting heavy separators | Actual47browser error/styles retained; pinned Owl old/new close differential, permanent required-prop regression and10identity checks pass. Installed48 still pending | Bounded template/CSS correction; verify real callback/focus and actual row colors in both themes | Shared palette/list remain owned and tested |
| Owned web shell/context, account/help, native list/form/control-panel and overlay presentation (unbuilt19.0.2.47.0) | Compose Meridian's shared patterns through native slots/controllers, isolated rail preferences and optional trusted context; use measured neutral roles and one collection scroll/footer owner | App-specific core queries, DOM portals for record identity, replacement persistence, browser source injection or reference mock data |128affected Node/29Python source checks;26actual Owl templates and seven mounted fake-DOM scenarios; unchanged freeze122/11. Installed visuals/contrast/scrolling still required | Native slot and layout changes require actual old-app/core-maintenance and new-app/zoom/RTL qualification; no authority/save/leave guard removed | Re-review these shared consumers if their rendering contracts change |
| Owned `web` shell, Dialog, command palette and user-menu presentation (provisional19.0.2.13.0) | First real in-app inspection exposed missing native-context focus/Escape handling and accessible dialog/combobox names. Add a normal guarded light/dark control over existing assets; omit unsupported vendor account/support menu registrations | App-specific CSS/keyboard patches, another theme engine, forced browser CSS, or source checks presented as rendered acceptance | Six new production-hook regressions fail against exact old source; nine focused JS checks and60affected core/staging/identity tests pass. Six real Owl templates compile; installed successor verification remains pending under ui-rendered-corrections-plan.md | Bounded presentation/overlay semantics; preserve native/custom leave guards and explicitly retest stacked dialogs, themes and navigation after normal maintenance | The owned shared UI keeps these behaviors; re-review actual consumers before changing this presentation boundary |
| `.gitignore` | Ignore generated local secrets/state; allow tracked product Docker/Node configuration otherwise hidden by upstream global patterns | Force-add every future file and risk hidden dependency locks | `git check-ignore` plus clean staged-file inspection before commits | Low; append-only product packaging rules | Upstream patterns no longer hide required product configs |
| `odoo/tools/parse_version.py` (generated R1 distribution only) | The pinned eight-digit padding misorders canonical0.99999999.0 and0.100000000.0. Width-prefixed decimal keys preserve the spec's package/native order, native alpha/final rules and tuple shape. SDK native_versions.py pins source71eeb208 and resultdfbad4b8; mp_compat1.1/core maintenance required | Narrowing accepted versions, changing native spelling, broad upstream deployment permission or import-order-dependent runtime monkeypatches | ADR0021; original counterexample retained, pinned upstream self-vectors/legacy corpus/wide fields and exact positive/forged/downgrade transition tests pass at source; actual0afd445c parser/applicability and exact core96a53908/compat1.1/retained state qualification pass in resolution-matrix/qualification.json; actual adjacent/skipped/fresh/wide DB/script VER-02 matrix24scripts/4DBs/current SDK audit also pass in migration-order-rollout-01/qualification.json | Medium; internal native comparison keys change, so actual applicability/migrations and versioned startup must be qualified | Upstream parser compares unrestricted numeric fields correctly; re-review new upstream source and remove exact exception together |
| `platform_addons/mp_shell/models/assets.py` (adapter; no upstream source edit) | Retain prior public host bundle attachment metadata so native checksum URLs keep serving their original bytes; delegate every unrelated/debug bundle | Replacing native assets/CRUD, a separate cache server, or accepting stale-URL redirects | 12 focused factory/preflight tests;65Windows/65Linux/78freeze; actual native clone, pre-ready fault/restore24, core25 and SDK26 direct old/new HTTP/readiness/replay qualified under ADR0018 | Medium; pinned private factory signature and native bundle constructor are copied through a narrow override | Upstream supplies configurable version retention/exact old URL serving or this seam changes |
| `odoo/addons/base/data/ir_module_category_data.xml` (generated distribution only) | Base bootstrap references categories normally generated when discovering excluded business addons; first curated boot failed on `base.module_category_services_timesheets` | Shipping ERP code just to create categories, deleting catalog records, or modifying ORM/loader behavior | `python -m unittest discover -s tests -p test_distribution_metadata.py`; fresh curated boot required | Low; static reference closure; builder fails if XML layout changes | Upstream base data becomes self-contained without full addon discovery |

| `platform_addons/mp_identity/models/scoped.py`, `platform_addons/mp_core/attachments.py` (owned adapters; no upstream edit) | Native id-only web_read skips read; public/token binary shortcuts skip normal access; native scalar field cache is shared across environments. Explicit entry/stream/pre-cache-field guards keep workspace IDs, field values and unsupported legacy attachments behind scope checks | Replacing native views/binary routes, permitting token metadata to override workspace policy, or claiming a native-code sandbox | ADR0039/0040; installed old-image HTTP/native-stream counterexamples, source52/freeze97 and exact core18/identity1.3 candidate; actual core18/19 installed regressions qualified (cached-fields-01/qualification.json) | Medium; web_read and binary hook signatures are pinned upstream seams | Upstream uniformly enforces these hooks before the shortcuts, or a future supported attachment profile supplies an explicitly reviewed scope adapter |
| `platform_addons/mp_identity/read_window.py`, `models/scoped.py` (owned adapter; no upstream edit) | Core19's necessary pre-cache guards amplify a24-row native list to519SQL queries. Finite20ms serialization snapshots reuse validated authority on the exact environment/actor/workspace/model/IDs/cursor/thread; native `thread.query_hooks` invalidates on mutating/multi-statement SQL, `Environment._field_dirty` disables reuse. Entries/writes and standalone scalar access remain guarded | Global authority/result cache, skipping record checks, replacing native lists, or relaxing the performance target | ADR0043; revised candidate25actual native isolation/revocation/context/expiry/error cases,52host/97freeze; candidate native24list123SQL. Actual28/129/55native31HTTP+Canvas and preservation qualified in read-window-02; HTTP/10k performance target remains | Medium; private profiler-hook and dirty-state seams are pinned upstream dependencies; trusted SQL/functions remain trusted, no sandbox claim | Upstream supplies a suitable finite authorization batch hook, or profiler/environment signatures change; re-review and requalify before changing the upstream pin |

ADR0046 dependency maintenance: `deploy/requirements-py312.in`/`.lock` and R1/build/worker locks deliberately replace fourteen old substrate package selections (thirteen upgrades and the existing native PyPDF2→pypdf adapter), with reviewed exact metadata and registry hashes; unrelated versions are preserved. Pinned upstream source and `requirements.txt` remain unchanged. Build helpers add existing packaging26.3 for wheel0.48; worker bootstrap pip becomes an explicit pin. This is a distribution dependency deviation, not an upstream source patch or sandbox claim. See `evidence/G7/20261103-security-locks-01/static-resolution.json` and `applied-locks.json`; actual candidate build/native/lifecycle/security qualification remains pending. Re-review on upstream/runtime dependency changes, retain old immutable image for recovery.

ADR0048 proxy packaging: deploy/proxy.Dockerfile keeps the exact official nginx base/binary and applies four signed, hash-locked Alpine binary package updates (three origins). This is owned distribution packaging, not an upstream nginx/Odoo source edit. Current candidate-only source/solution evidence: evidence/G7/20261104-support-images-01/proxy-image-qualification.json; actual ingress/release selection remain required. Retain base notices and exact APK inputs; remove this overlay when a qualified official image contains the fixes.

ADR0048 selection: proxydece6f passes currentdev/isolatedproductionsecurity/native/transport (G7/20261104-production-profile-01/qualification.json). Compose/runtime defaultsselectit; working sitesunchanged. Host-onlydeploy/build_proxy.py rebuildsexactofflinecontext fromsigned/hashlockedinputs; no upstream/Odoo/nginx sourceedit ornewapp runtimehelper. FinalG7provenance/security/kit remains pending.

ADR0052 adds an optional code-only maintenance build from an exact independently selected qualified application image. It materializes a fresh allowlisted source distribution while preserving the actual Python/OS environment; normal staged source/version/approval/recovery checks remain enforced. This is owned distribution packaging, with no upstream source edit. Core23 admission/installed maintenance preserves all77 actual Python distribution digests and the lock; the first newly compiled candidate was refused and retired. See G7/20261104-core23-uninstall-image-03/candidate-admission.json and core23-maintenance-01/preservation.json. Retain the immutable dependency base and its source/notices as release inputs; full final reproducibility/provenance remains required.

ADR0057 corrects measured UI09 defects in owned `mp_shell` adapters only:
muted text/all heading contrast, native field focus rings, preservation of the
existing Odoo close image/dark filter, document language/direction and Settings
translations. Native RPC/release/retirement/authority/activation/View seams stay
byte-exact. No stock Odoo source, packaged plugin or public contract change.
Core24/Shell11 source passes affected host checks; normal immutable candidate
admission/independent core upgrade and installed qualification remain required.
See G7/20261104-ui-qualification-01/ui09-diagnostics.json/source24-checks.json.
Remove or simplify these adapters when retained upstream presentation satisfies
the chosen platform theme and language requirements, with actual UI evidence.

The stock WebClient release carries Node and the hash-locked RTLCSS package
set from `deploy/Dockerfile.stock-rtl`. Odoo uses the compiler to mirror its
native styles. The release retains Node and package notices. This distribution
change leaves the pinned Odoo source intact. The workspace trigger focus and
Arabic messages live in the platform addons.

The stock RTL launcher disables JIT and bounds the Node heap within Odoo's
640 MiB HTTP worker address space. The owned asset adapter versions the two
native RTL bundles with the release inventory and lets Odoo clean their old
attachments. The operator verifies the mirrored screen CSS before opening
traffic. Earlier profile versions keep their original asset preparation.

AR-02 owned-fork extraction (8 November2026, qualification pending): directly
changed inherited base/base_setup/html_editor/mail rather than introducing
another override layer. Removed vendor sales catalog/store links and unavailable
settings; removed hosted AI/media search/download routes and their editor controls.
Moved the generic link metadata helper from mail/tools to html_editor/tools;
editor collaboration handles absent optional mail ICE service. Mail now names an
optional communication service. Full Discuss action/public entry points and
POP/IMAP polling/model/field/ACL/cron/settings moved into applications/mp_discuss
and applications/mp_mail_gateway, preserving original licensing. Shared chatter,
activities, notifications and conversation widgets/models remain services. Added
native window-action fallback when Discuss is absent. Moved useful fetchmail tests
to their owning app. Base1.4, settings/editor1.1 and mail1.20 mark changed sources.
This is our fork, not an external-addon compatibility layer. Sealed core46 stays
unchanged; source validation alone does not qualify populated migration/recovery.

AR-02 follow-through: tours1.1 now explicitly optional; extracted generic
MockRequest into engine tests so web/mail regressions do not require the excluded
HTTP-routing application. Web1.1 removes vendor Enterprise upgrade boolean/dialog
and only its sales-specific tests; highlight/native layout retained. Mail menu
ownership corrected for full-workspace Call History. Native core13, Maintenance15
and explicit communication17 profiles passed onb51ce4ac. Six retained native
editor/polling tests passed0failures/errors;15affected host tests passed. Public
ownership map36gateway/14Discuss IDs is a migration input, not a grant or ID guess.
Populated46 transition/recovery remains unqualified until AR-04.

AR-03 owned source checkpoint: engine/bootstrap/config discovery now resolves
framework/app/example roots without a duplicate vendor tree; production source
paths and installed flat paths are distinct. Regular addon package replaces
namespace assumptions; removed obsolete namespace invalidation mutation after
CLI reproduction. Builder/reference packaging/source-input/operator byte guards
and Docker allowlist use owned roots. Native numeric-width fix is in engine,
original exact preimage kept solely as a regression fixture; fresh builds do not
pretend to generate it.22inherited native fixture dirs retained, legacy merchant/
Enterprise fixture replaced by owned permission/identity/native-view flow; legacy
RPC transport test-only and not auto-installed or shipped.628unused production
addons and IAP source removed, obsolete vendor installer recipes retired. Root
notices/Git provenance retained. Current image4fc56557 is a qualified layout
prototype, not a new sealed release or a populated migration pass.

AR-04 gateway1.1 removes the unsupported local XML-RPC pipe selection, script
default and executable entry; stored script settings remain readonly and local
records prevent transition before mutation. POP/IMAP retained. The owned46→47
recipe uses old code's module API for IAP retirement, preserves actual mail
record IDs under the extracted owners and retains aliases for our own R1 data.
Raw private retirement archive and site-scoped lifecycle authority are owned
platform additions. Prototypebba actual migration/closed fault/fresh46restore/
separate resume passed; final populated job/release qualification remains open.

## AT native application background support (candidate core48)

Owned mp_core/SDK changes add explicit native authority, site-native metadata and
managed native partitions; owned Aurora addon adds reminder/inbox behavior and its
declared data migration. No inherited engine patch in this item. Existing source
notices retained. Qualification is pending AT-03/04; sealed47/46 remain unchanged.

## Shared interface foundation

The backend web asset manifest includes the platform presentation stylesheet
and query disclosure. The native search-menu trigger has a sliders icon and an
accessible name. The list, form, search and menu controllers retain their
inherited behavior. Geist Latin variable is served locally under its accompanying
SIL Open Font License in `web/static/lib/geist/LICENSE`.

UI-D03 replaces the stock-profile navbar presentation with a shared Owl shell while retaining the menu/action services and main component/overlay container. Scoped menu data is supplied by mp_core. The original NavBar path remains for the optional reference profile and bare-web consumers. Web presentation maintenance is versioned and constrained to static assets plus the manifest; original source attribution remains.

UI-D05 adds shared page/context/feedback components and semantic light/dark
presentation tokens under `web/static/src/interface`. Native fields, model
controllers and action/leave hooks retain their behavior. The maintenance guard
admits append-only explicit references to inventoried local shared-interface
assets, preserving all other manifest declarations and existing asset order.
Source implementation is not installed or browser qualification.


ADR0089 corrects the owned web native appearance reader to select the existing dark bundle only for the exact dark preference value; missing/unknown values remain light. Existing asset templates, session/authorization and notices remain. Maintenance admits only the reviewed full-file before/after pair with strict versions and normal independent approval/checkpoint. Actual core13 failure retained; core14 installed theme proof pending.


Actual dark-bundle audit exposed inherited fixed light native table/header/modal/input/label colors. Core0.2.15 bridges these existing presentation variables and screen-only heading/label styles to the shared semantic light/dark tokens. No native controller, field, print, authority or data behavior changes; notices retained. Installed theme requalification remains required.


Core0.2.16 reworks owned native collection presentation with existing ControlPanel display/slots and list model pagination callback: shared bounded footer pagination, grouped/embedded consumer placement, explicit narrow query and end create action. Native non-table form record traversal remains separate. Owned router/WebClient preserves dirty action/URL consistency using presentation-only history positions and ordinary leave guards; no actor/workspace/permission authority is derived from this metadata. Theme files add native color-scheme and visible close SVG/focus. No wire/backend/storage/notice changes. Actual installed qualification pending.


Core0.2.17 replaces fixed native group/facet colour utilities with semantic shared styles and expands the existing primary-action mapping to native dialogs. Uniform rows retain hover/selection; native query controls shrink/wrap and group counts are labelled through an optional presentation flag on existing paginator producers. No query/model/authorization changes; original source notices retained.


Core0.2.18 adds the shared native record ControlPanel variant and explicit loaded-record navigation while retaining FormController save/load/leave and model code. Native status controls name state/actions, prevent duplicate pending commands, retain validation disabled state after the existing button executor, and return focus without taking it from another dialog. Breadcrumb heading semantics, native chooser names/keyboard, native input title fallback and semantic checkbox/outline/scrollbar/form styles are owned web presentation edits. The native label precedence was checked against W3C HTML-AAM; no backend/data/schema/authority change or notice removal.

15November2026 record follow-up: owned web screen rules override the inherited desktop navigation flex basis and sheet/section colours. Existing form model/save/leave callbacks unchanged. Core private native error redaction maps only actual PublicError CONFLICT to fixed UserError guidance, keeping redaction/exception/JSON-RPC boundaries. Source tests/compiler pass; installed successor proof pending under ui-record-polish-followup-plan.md.

15November2026 read-first native presentation: owned FormController uses existing readonly/edit modes for standard full-page records and normal callback success/refusal; New/dialog/custom persistence/forcedreadonly behavior retained. Optional clean-editing status and requested-transition focus; old native leave/visibility/unload save machinery unchanged. Ordinary WarningDialog selects existing md size. This is an intentional owned interaction choice, not upstream compatibility preservation or an authority boundary. Source/component proofs pass; installed successor pending under ui-native-record-read-first-plan.md.

15November2026: Owned native Field/controller focus readiness and optional Dialog slots fix; separate reactive field patch is acknowledged once, no polling. Actual installed21 counterexamples precede source22; persistence, guards, app archives and authority unchanged.

15November2026 core23 source: actual390pxmissingEdit reproduced old adaptive CSS assumption. Scope hiding to realadaptive dropdown; legacy overflow unchanged, sharedtable/record actions wrap. Reusable linked-record header/list/row/status CSS usesexistingtokens/logical/focus; no newJSexport/framework/businessrule.10identity/freeze12211/pinnedCSSRTL pass,54unchangedJSattested. Plan preceded5shippedfiles/unchangedapps. Installed narrow proof pending.

15November2026 core24 source: restore generic native action layout at nested shared-shell mount through same extractedSassmixin asdirectmount, exact17legacydeclarationmaps/nativeprintCSS retained,8newmatching rules,actualRTL compiled. Sharedrelatedactions min34desktop44narrow/wrapping.10identity/freeze12211 pass;54core80appJS retained unchanged. No data/API/authority/app bytes change; original390clip andundersizedtarget witnesses preserved. Normal immutable installed proof next per freshplan.

15November2026: Core24/config22 normal maintenance completed176.672s, five shipped files only/all five app pins unchanged. Actual390px wheel and focused PageDown reach last task, long record bottom and native table footer; pages1-80/81-160/161-165. Targets34desktop/44narrow. Task dialog and Documents retain their own scrolling; named Preferences open/Discard and keyboard native Edit/Cancel remain correct. All18tables/FULLhistory/tenother targets exact; no business/authority writes. Sparse contact reading layout remains the next Meridian-driven refinement. Full UI matrix/canonical open, UI0of4.

15November2026: Core25/config24/image7e5a0513 native link correction installed159.047s;4shipped files/all5app archives/Python exact,14layer audit. Actual link6.92to1light/9.04dark, visible tokenfocus, native Enter organization/Back and390nooverflow pass. Hover source-only, no pointer claim. Zero-write pass18tables/FULLhistory/tenothers exact. Then fresh originalD05 native Save intent: Sample82Notes3to4 clarification, oneevent; stale secondtab refused/named bounded medium warning, draft retained until explicitDiscard/reload; other165partners/17tables/allpriorhistory/tenothers exact. Originaltask2 retained. No authority/locale/source-app changes. UI0of4/full original matrix/canonical open.

15November2026 source26: authenticated webclient bootstrap declares server-validated native language/direction and removes user-scalable=no; all other template bytes/scripts preserved by exact reversal/hash test. ADR0090 admits only its exact reviewed source pair for versioned core maintenance, no arbitrary templates/backend path. Source52 focused tests passed103.894s, freeze122/11 unchanged. Installed rendering/RTL/zoom proof remains pending.

15November2026: Core26/config25 installed152.828s/image1ce61f29;5exactsourcefiles/all5app archives/Python unchanged.52source tests103.894s/freeze12211. ActualHTML en-US/ltr, ar-001/rtl and unrestricted viewport pass. Firstlocale switch still loads preceding language stylesheet: Arabicbodyltr; restoringEnglishbodyrtl until another normalreload. RTL NOTaccepted. Both normalpreferences changes scopedonlyAlice6 language, full user/group/lang semantics restored;18tables/fullhistory/Sample4/tenothers exact. No activefixture/draft/operation. Source trace session_info updates session.context while assets consume currentenv.lang; fresh producer/consumer differential+request-language synchronization next.

15November2026 source27: synchronize validated current-user language onto the existing request context before native assets; actual native rendering/request-merge/asset-consumer differential preserves old failure and proves both directions/cache modes. Exact reviewed reader pair retains prior source pairs; no broad backend admission. Shared readonly full-page sheets with direct shared-card children lose redundant outer framing only on screen. Native Edit/new/dialog/ordinary forms/print unchanged.59 affected tests pass104.926s; separate locked Sass/RTL old and non-screen maps exact/one selector added; freeze122files11rows passed. Six shipped files including identities; no installed27 claim yet.

15November2026: web native TextField readonly span/textarea use dir=auto and shared plaintext pattern; input hooks/value/escaping unchanged. Existing identifier direction is protected from RTL compiler flipping. Source plan ui-content-direction-plan.md. Licensed upstream/Geist/notices unchanged; installed qualification pending.

15November2026 candidate0.2.29: owned web presentation now uses one local Owl SVG primitive (Lucide0.468.0 geometry; exact ISC and Feather attribution in framework_addons/web/static/lib/lucide/LICENSE plus module SHA provenance). Native menu/action/form/model/approval paths remain the owners; migrated chrome retains labels and image-path icons. Per-user/app presentation-only collapse and common native/shared breadcrumbs keep work area/drafts mounted and delegate existing leave lifecycle; standard modified links preserved. Screen-only brand/contrast reconciliation retains semantic error/warning/success and identical print rules. Existing FA/OI assets remain for unmigrated uses, not removed wholesale. Source/preview proof only, installed maintenance qualification pending; no provenance/licence/wire/security bypass.

15November2026 core30 source: actual installed029 frontend-lazy dependency graph identified CommandPalette->sharedIcon absent from that root. ADR0092 one native common group now supplies unchanged Icon/data/XML and relocated SVG/loading styles to backend_core and frontend, minimal remains independent. Maintenance fence extended ONLY for exact old3/new4/Owl-anchored move plus valid inventory; native declarations/othergroups/order/default append/approval/checkpoint remain guarded.7actual-native-consumer+policy cases,9existingstaging,7nativeversion pass; pinned Sass/RTL complete declaration maps identical inclprint/motion; frozenwire unchanged. New030 identities, no private app relabel, no030 build/upgrade yet. Retain old29 images/cohort/error evidence; UI0/4/full goal open.

15November2026 unpublished core31: actual installed resize finding reproduced against old source using mounted Owl+real native useService/reactive UI service, without action-bus events. Native Shell and custom AppLayout now subscribe to ui.isSmall; stored desktop preference/content/drafts/portal/focus stay intact in both resize directions. Same mounted regression now passes,28 native templates compile,22 affected Node+7native-version tests pass. New unit fixture needed document/contains boundary; old failed log retained. Three coherent31identities reserved, no31 image/installed claim; current18730 remains30/config3/787f. No CSS/business/authority/wire changes. Future creation/detail delivery can share this unpublished candidate; no cosmetic image loop.

15November2026 creation31: owned native action/list/form presentation adds explicit creation surfaces using the existing View/model and guarded Dialog lifecycle. Optional preventAutoSave/onRecordReady only affect opted-in creation; ordinary form defaults and existing-record routing remain. Original source/license notices preserved. Source and installed evidence are separate; see ui-creation-surfaces-plan.md and ADR0093.

15November2026 creation32: scope desktop fullscreen and flush side-sheet geometry to opt-in creation surfaces, keeping inherited ordinary Dialog and print declarations. Expanded creation ignores drag offsets without changing the mounted native form/model. Native compact creation selects existing md size. Source proof separate from installed; no upstream notices removed.

15November2026 record33: add presentation-only native record tabs/cards; optional recordBodyTitle selects compact inline breadcrumbs while ordinary native form controls, validation, CAS, print and callbacks retain defaults. No upstream licence/provenance removed.

15November2026 record34: model-derived opt-in informational native frame/traversal presentation; ordinary forms and native state/handlers retained. Normalize shared card margin, use pinned semantic SVG sort/menu/account marks and accurate aria-sort. Existing native sort behavior assertions retained with current SVG/ARIA expectations. No attribution/licence changes.

15November2026 final35: shared native informational cascade/heading/danger presentation corrections; native identity browser transports existing pinned scope/release headers to the exact readonly breadcrumb model-name endpoint. Server ACL/scope/release guards unchanged; attribution and notices retained.

15November2026 source36: shared dir=auto title alignment uses validated document-root direction with basic supported left/right declarations, retained unchanged by RTL compilation. No locale/authority/action behavior or notices changed.

15November2026 source37: the existing native error-handler registry presents actual
missing/access RPC failures as one deduplicated, fixed translated unavailable-page
dialog. Explicit application dialog/notification choices remain authoritative;
unexpected errors retain opt-in diagnostics. Shell's redundant blocking modal is
removed, retaining its hidden mounted action canvas and inline recovery. Native
Dialog back/expand/close and diagnostic-copy controls use exact already-pinned
Lucide SVG geometry in the shared header template, preserving native callers,
callbacks, slots and notices. No request retry, automatic navigation, draft
save/discard, server authority or recovery change. Source checks pass; installed
qualification is pending under ui-unavailable-page-correction-plan.md.

15November2026 source38: Shell's existing fallback title/description now distinguish
available app destinations with no selected page from a genuinely empty workspace.
The rendered source37 missing-model route supplied the counterexample. Existing
blocked-access branch, action mount, navigation and draft behavior are unchanged.
No vendor notice, attribution, asset dependency or application byte changed.

15November2026 source39: an empty Shell action canvas keeps its mounted slot and
access-hidden behavior but no longer consumes free flex space above the workspace
card. Loaded controllers/drafts retain their allocation. Existing native Dialog
header buttons gain component-owned34px/44px hit boxes, keeping pinned geometry,
callbacks, labels, slots and t-call consumers. Original native Sass declarations,
attribution and notices remain; actual installed geometry is required next.

15November2026 source40: the existing screen-only foundation bridge maps native
Bootstrap button/focus-ring variables to the shared2px theme focus token. This
replaces the measured inherited lavender glow while retaining native focus and
button callbacks, semantic backgrounds, geometry and print. No JavaScript,
upstream Sass declaration, licence or notice change.

16November2026 source41: screen-only owned foundation bridges existing light/dark
link RGB tokens into Bootstrap's actual RGBA anchor consumers, and maps only the
native select background-image variable to the same original geometry with
shared muted strokes. Validation's second image layer, native selection/focus,
layout, routing, print, backend/authority/recovery and all licences/notices remain
unchanged. SDK/core/web identities advance to0.2.41/19.0.0.2.41/19.0.2.41.0.
Normal populated/empty maintenance and independent Taskfiles0.1.7 palette upgrade,
real two-theme link/select/metadata measurements and final041 canonical qualify
the exact changes; see ui-final-link-select-contrast-plan and installed41/final041
evidence. This supersedes earlier pending paint checks, not their failure traces.

16 November2026 Meridian phase1 source42: owned shell now composes the top bar
before the app rail, separates declared workspace systray contributions from
trailing utilities and centers the command track. Native and custom context
controls move into their pane headers with focus restored after remount.
Shared tokens and native header padding align the directory; a generic identity
field renders loaded escaped text and delegates editing to CharField.
SDK/core/web identities advance to0.2.42/19.0.0.2.42/19.0.2.42.0. Existing action,
workspace and permission services remain the behavior owners. Targeted source
checks pass; installed asset/visual qualification remains pending in
docs/meridian-phase1-plan.md. Existing attribution and licence files retained.

16November2026 Meridian phase1 successor43 addresses two defects seen in the
installed42 native list. The legacy character-cell truncation selector excludes
the structured generic identity widget. The shared actions header fits its
chooser and padding at desktop and coarse/narrow sizes. Core43/native43/web43
record these shipped changes.21 targeted source checks pass; installed43 is
pending. Original42 images and captured failures remain retained.

16November2026 Meridian phase1 successor44: installed43 confirmed structured
identity fixed but exposed the native column-width producer writing12px content
width despite the CSS minimum. computeWidths now includes the declared action
header minimum after subtracting padding, preserving the legacy deletion floor.
Read-only list cells use6px block padding under the existing44px row token.
SDK/core/web44 version the shipped change. Three real algorithm regressions
and21 affected source checks pass; installed44 remains pending.

16November2026 Meridian phase1 successor45 refines shared identity typography
from19/16px to18/13px line heights and isolates displayed name/secondary values
with bdi. The shared screen foundation inherits the reference's cv11/ss01 font
features via a token. SDK/core/web45 record the shipped bytes.6 Node/21 Python
checks pass, along with the unchanged contract freeze. Installed45 remains
pending; this does not claim a new data or permission behavior.

16November2026 Meridian phase1 successor46 corrects the owned list renderer's
width budget: computed outer table borders are included before column widths
freeze, with half-width collapsed edges. Actual production-hook counterexamples
fail on45 for the observed863px parent and pass after correction, including
fractional borders, borderless/separate edges and genuine narrow overflow.
No overflow-hiding CSS, app branch or authority behavior changed. SDK/core/web46
record shipped bytes; installed visual verification remains required.

16November2026 phase2 source47 introduces app-independent ContextNav, Badge,
RecordHeader/Layout exports and native Shell consumption. Native neutral badge
roles now follow light/dark tokens; existing semantic/color-field meaning is
retained. The ordinary menu/action/leave services remain owners; no private app
or model query enters base UI. Source component/hook, actual asset consumer and
pinned Owl checks pass. This is an unfinished source checkpoint, not an image
or installed47qualification. Core/web/SDK47 are reserved for the upcoming
coherent phase2 candidate; retain attribution and current immutable46image.


## Meridian core49: scoped native form identity and validated focus

The owned web FormCompiler/Renderer now names DOM field IDs per renderer,
including explicit/group/setting labels and autofocus. Controller-owned
button-box subviews have their own identity provider. Architecture metadata
keys remain unchanged. Removed the old nested-dialog workaround which removed
background field IDs but left their labels attached to another form's input.
Native failed-save paths request scoped invalid-field focus; actual Field
patch readiness supplies input aria-invalid state and completes focus after
validation. Drafts, save/retry/uncertainty/CAS and authorization remain native.
Top-level list footer restores optional rows-per-page through existing model
onUpdate; embedded/group paging unchanged. Icon metadata underscores resolve
existing pinned geometry; shared reference card metrics/narrow palette refined.
Identities advance platform0.2.49/core19.0.0.2.49/web19.0.2.49.0. Partners12
archive/backend/schema/security unchanged.139Node/29Python cases,27actual Owl
templates/seven composition cases and eight actual compiler/form/label/Field/
Setting/save-focus fake-DOM scenarios pass. Freeze122files/11rows unchanged.
Source evidence .local/meridian-phase2-source049-01; installed proof pending.


## Meridian core50: real helper import correction

Installed49 revealed uniqueId was incorrectly imported from utils/strings in
FormController and FormRenderer. Use the actual existing utils/functions export,
matching shared ContextNav. No further behavior/geometry change from49; three
identities advance50. Added a permanent check resolving both real declared
imports and using the actual exported helper, plus actual helper loading in the
compiled-form witness.140Node/29Python/27Owl templates/seven composition/eight
form scenarios pass. Original49 error/screenshot retained under
.local/meridian-phase2-browser049-01. Installed49 real native 10+5 paging passes,
but form fidelity is invalidated until corrected50 is installed and checked.


## Meridian core51: native control-panel theme bridge

Installed dark record header used literal Bootstrap rgb222/226/230 while other
shared borders used alpha neutral. Bind the existing --ControlPanel-border-bottom
hook to the shared --mp-ui-line token, screen-only in foundation.css. No native
DOM/JS/paging/forms/behavior changes. Three identities advance51. Ten affected
identity/compatibility checks and freeze122/11 pass; actual dark/light installed
border measurement remains required. Partners12 archive/data unchanged.


## Meridian core52: native collection selection composition

Actual selected-state audit found blue Bootstrap row/summary, hidden query,
unlabeled legacy clear glyph and old mobile selection overlay. Keep native
SelectionBox/root selection/count/domain callbacks; use pinned Icon/clear label
and polite status, neutral shared --mp-ui-selection role, query retained with
an adjacent stacked selection row. Honor explicit author layoutActions=false.
Remove only old mobile fixed overlay/faded shell and Bootstrap table-info row
class, retaining semantic selection/editing/decorations/keyboard model behavior.
Core51 divider bridge retained;51 candidate built only, never deployed. Three
identities advance52, direct current50->52 maintenance planned.144Node29Python/
28Owl templates/nine mounted composition/eight form checks pass, freeze122/11.
First private mount cleared raw fixture objects without proxy notification;
corrected fake method to mutate its receiver, original trace retained. No real
installed52 claim yet; Partners12 backend/schema/archive/security unchanged.
## Meridian core53: native related-record return and action glyphs

Plain many2one current-page links keep the fresh get_formview_action call and
may prefer an exact real inactive form ancestor. The action service matches
model, exported-ID precedence, selected form and complete effective context,
then calls its existing restore/leave/reconstruction path. Unknown properties,
nonempty domains, explicit stack/props/leave options and dialogs/new tabs fall
back normally. No app-specific keys, guessed URLs or label deduplication.
CogMenu's single-print and dynamic-icon paths now use the existing pinned Icon;
unarchive maps to existing archive geometry with its distinct action label.
Three shipped identities advance53.153Node/29Python cases, unchanged28-template
composition/eight actual compiled-form scenarios and actual CogMenu/Icon mounted
branches pass; freeze122files/11rows. The first helper test caught preprocessing's
normal empty domain and was corrected before packaging. Source proof only until
the successor is built, installed normally and reviewed against Meridian.

Installed53/config14 through normal85328ff0/hash1c7083fd; actual plain related
link restores Acme and its1/16 pager, Back returns the contact, menu labels have
decorative SVG/zero font nodes. Seven tables/protected14/private5/source4051 exact.
Existing modified-anchor href omits workspace and safely opens Choose workspace;
this remains a phase2 UX gap. Fast empty-draft leave observation is unproven,
not a passed installed guard check; no business save/data change. Evidence is
.local/meridian-phase2-browser053-01. Full phase2 acceptance remains open.

## Meridian core54: scoped native links and pending-input leave

Router stateToUrl gains optional inheritLockedKeys; default behavior is exact.
Opted many2one/breadcrumb/new-window URL producers carry only existing router
locked keys. Existing native anchor modifier/copy/context-menu handling stays;
no generic view parses workspace or inherits unrelated route/action parameters.
FormController.beforeLeave now flushes the existing root.isDirty/NEED_LOCAL_CHANGES
seam before testing dirtiness; invalid parsed input also enters the normal save/
validation refusal path. Explicit forceLeave preserves discard behavior; create
preventAutoSave ownership remains. Creation close uses the existing discard
decision for invalid parsed input even with unchanged model data. No server,
grant, CAS, transaction or transport-uncertainty changes. Three identities54.

171Node/29Python cases,28Owl templates/nine composition/eight actual compiled
forms/actual CogMenu branches and freeze122/11 pass. Actual input hook, useBus,
record isDirty and model _askChanges execute together with explicit update/save
boundaries. This source proof is distinct from installed form/modified-link
qualification; current populated image remains53 until normal maintenance.

Installed54 via06522669/hash3d2dd1b3/config15. Actual required-empty input refuses
parent leave with focus/aria-invalid, and scoped Ctrl-click opens the destination.
Native sheet/full-page creates, one CAS-winning edit and one stale refusal are
verified with original16 rows/18events and authority unchanged; current18/21.
Alice/B viewer has no create and foreign A read is denied, operator/A restored.
Actual Discard retains its local snapshot until explicit reopen, not latest-read
semantics. Bare model deep link has no context sidebar, a retained composition
finding. Current native200%/empty-core/remaining phase2 gates are not accepted.
Evidence .local/meridian-phase2-browser054-01 and creation054-01.

## Meridian core55: isolate owned plain header/collection text

PageHeader's title/eyebrow/subtitle and native ControlPanel's description/meta
remain escaped plain strings, now inside bdi following ContextNav.Label's
existing pattern. Blocks keep their alignment, classes, count and slots. Do not
force direction on arbitrary author slots: Partners owns its footer string and
must isolate it there. No CSS direction injection, API/schema/model/permission
change. Three shipped identities55.171Node/29Python cases,30Owl templates/ten
mounted composition scenarios/eight compiled forms/CogMenu and freeze122/11 pass.
Actual PageHeader and native control-panel consumer witnesses preserve escaped
text/count/query/selection callbacks. Installed Arabic ordering remains required;
compact Partners13 phone defect is a separate pending author-view correction.


## Meridian core56: isolate pagination range and failure text

TablePagination and RecordNavigation retain their status live region, tabindex,
compact aria-label and existing callbacks; owned escaped text is inside bdi.
Translated prose/fallback uses automatic first-strong direction; a valid compact
current/total numeric position uses LTR so RTL does not exchange its meaning.
Error text is isolated within existing alert blocks. No JS producer/count/page/
request/save/permission change. Three identities56, exact private Partners14.
Affected44Node/22Python pass;31actual Owl templates compile and mounted actual
pager consumers cover range/group/limited/empty/invalid/escaped error, compact
numeric/fallback/live label/focus and callback. Existing native Layout witnesses
retained.122-file/11-row freeze unchanged. Private expected separator em-dash was
corrected to producer middle-dot; original harness failure retained, production
unchanged by that correction. Installed Arabic proof still required.


Installed56 evidence:761ae526/config18 and b489ebfe/emptyconfig3 completed once.
Current realArabic page/record ranges pass; all business/authority data retained.
Final056 snapshot verifies both targets/protected sources. Source proof and real
native ordering are distinct; full phase2/zoom acceptance remains open.
