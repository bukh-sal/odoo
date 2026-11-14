# UI-D01: Meridian-based shared design direction

**Decision, 14 November.** Use the roomier study and restore the contextual sidebar to 264 px. Put shortcut reminders in help or the command palette. Group filters and keep search visible. The measurements below record the study before this decision. [Shared implementation and app recipe](ui-foundation-implementation.md).

Original visual study, 14 November 2026.
The first independently styled proposal was rejected by the user. It is archived
and is not being evolved. Start from Meridian's actual current style and change
only what has a clear reason. Branding remains a placeholder, not an adoption of
the Meridian name. [Pattern audit and decision matrix](ui-pattern-audit.md).

## Visual starting point

Keep Meridian's Geist typography, restrained neutral surfaces, icon vocabulary,
compact56px app rail, contextual sidebar, single search surface, app-owned primary
actions and quiet status accents. Keep its shared component/pattern approach,
not its mocked backend or fixed business-app catalogue. A context sheet, native
record view and custom app page should look like parts of one product.

The replacement study is an isolated copy of the actual Meridian static build;
the original checkout is unchanged. It uses the original fonts/components/icons
and a small separately recorded CSS refinement layer. Font licenses are retained.
It is neither a newly implemented shell nor proof of the platform features shown
by the prototype. Chat, accounting, presence and attention badges remain simulated.
React/Tailwind are not being added to the platform through this study.

## First restrained refinement study

The matched comparison uses the same tab, dataset, viewport1309x909CSSpx and
devicePixelRatio~0.99. User/browser scaling was not reset. Values were measured
from actual rendered DOM, not inferred from screenshots.

| Element | Original Meridian | Refinement | Reason / visual judgment |
| --- | --- | --- | --- |
| Font and icon/component language | Geist + original icons/components | Unchanged | Preserve the stronger baseline. Production Arabic font/fallback coverage still needs a deliberate decision. |
| Global app rail |56px icon rail | Unchanged | Preserve current Meridian shell. Discoverability/tooltip/All apps behavior needs actual production testing. |
| Contextual sidebar |264px |240px | Return24px to working content while retaining useful hierarchy. Long/translated destinations still need validation. |
| Page heading |24px /30px line |26px /34px line | Strengthen page identity slightly without a new visual style. |
| Task row |40px |44px | More readable scanning/targets; slightly fewer rows per screen. This density choice needs user judgment. |
| Task title |13px |13.5px | Small legibility improvement while keeping the compact product character. |
| Primary page action |28px high |34px high | Give the page's primary action a clearer target/hierarchy. |
| Global search |32px high |36px high | Slightly easier target; keep the same component/location. |
| Metadata section text |10.5px |11px | Modest legibility increase, still subordinate. |
| Surface hierarchy | Mostly near-grey surfaces | Slightly lighter background + white content/popovers | Distinguish content and overlays without heavier borders or a new palette. |

No final numeric token scale, colour palette or density default is frozen here.
The prototype's scan claims do not replace measured contrast/keyboard/RTL checks
for our future implementation. A small CSS study is especially not a full mobile
or Arabic redesign. The first rejected A/B rail studies are excluded from this
direction; rail selection is no longer being presented as the primary decision.

## Screenshot review packet

Private local packet: `.local/ui-design-audit-01/screenshots/`.
Screenshots are unmodified browser captures. Source/provenance/measurements are
in `.local/ui-design-audit-01/{meridian-study-provenance,browser-observations}.json`.

| Capture | What it establishes | What it does not establish |
| --- | --- | --- |
| `meridian-baseline-matched.jpg` | Actual original Meridian at matched viewport/data | Installed platform shell or real business authority |
| `meridian-refined-matched.jpg` | Same original components with the explicit refinements above | User visual acceptance or production implementation |
| `meridian-refined-record.jpg` | Same style carries into Meridian's customer record | That all related tabs/actions exist in the current native app |
| `meridian-refined-drawer.jpg` | Reference contextual detail presentation with refinement layer | That a generic supported Drawer API has already shipped |
| `current-native-list.png`, `current-native-form.png` | Actual inherited Partners list/form on UI-C01; source behavior retained | A planned new native renderer appearance |
| `current-workboard.png`, `current-documents-detail.png` | Actual custom app layouts and visible cohesion gap | Universal custom app/accessibility support |

Actual initial reference viewport was1600x1111/DPR~0.9; current native/custom
1346x790/DPR~1.1. Those audit captures are source observations, not matched pixel
comparisons. Only the new Meridian baseline/refinement pair has matched viewport.
The PNG-named early captures retain the screenshot API's original bytes; final
comparison files use its documented JPEG extension.

## Shared foundation available to every app

**Ownership:** a generic platform presentation foundation, independent of private
apps and optional reference `mp_shell`. Extract/adapt useful existing web/host
styles rather than forcing every app to import Workboard or Notes. Prefer the
existing web presentation boundary; exact package path is decided by the fresh
implementation plan. The default core remains the demonstrated eight addons.

**Three reusable levels:**

1. Framework-neutral semantic CSS tokens for surfaces/text/border/action/status/
   focus, type, spacing, radius, elevation, density, motion and layout. Light/dark
   and logical direction are designed together. Bridge the inherited Sass and
   Bootstrap values to those tokens so generated views use the same visual rules.
2. Owned Owl primitives or small adaptations of useful existing widgets: controls,
   field labels/messages, dropdowns/tooltips, overlays/drawer, query toolbar,
   page/record header, status/empty/error/draft/conflict patterns. Document imports,
   slots, keyboard contracts and scope instead of relying on private internal paths.
3. Native presentation adapters and app composition recipes: list/form/kanban,
   master-detail, related panels and immersive workspaces. Apps may compose rich
   business widgets and restrained accents; standard controls/chrome stay cohesive.

A component catalogue must show real states, long labels, density, theme, Arabic/
RTL and keyboard use. Prove it with native Partners plus two independent custom
apps before calling it reusable. A second framework, Web Components wrapper or
universal form/query engine is not a prerequisite.

## Shell and capability boundaries

- Global region: authenticated workspace identity, one app/command search surface,
  help/account, and only genuinely supported optional utilities. Do not copy
  mocked bell/chat/presence counts into an otherwise app-free core.
- App rail: actual available navigation contributions. Hidden backend/integration
  addons do not become visible applications merely because they are installed.
- Contextual sidebar: current app destinations/views/trees. Business lists,
  projects/statuses and counts remain app-owned and server-scoped.
- Canvas: one page header/action/query pattern, then app-specific useful work.
  Deep records may use native full pages or a shared safe contextual drawer.
- Visibility is presentation, not authority. Preserve current server membership,
  feature/grant/provider/release enforcement and optional-source denial behavior.
- Preserve current safe new-tab workspace switching until a unified native/custom
  safe-leave transition is implemented and qualified. Drafts are not copied into
  URLs or automatic browser persistence as part of a visual refresh.
- Default/empty core gets honest workspace/application-empty/own-job paths, not
  mandatory customers/tasks/chat. No business model becomes a shell requirement.

## Implementation order

The original review asked whether the slightly roomier Meridian refinement felt
better than the original compact density. The decision above closes that question. Rejection of the first proposal
is recorded for provenance.

After that direction is settled, activate one fresh implementation plan at a
time: foundation/token/native bridge; shell/navigation/overlays; native/custom
adoption; affected interaction/authority/assets/accessibility/lifecycle
qualification. Early real asset compilation belongs in delivery safeguards, not
as a substitute for doing the shared redesign. Preserve all old app/demo data,
source identities, source ownership and inherited attribution throughout.
