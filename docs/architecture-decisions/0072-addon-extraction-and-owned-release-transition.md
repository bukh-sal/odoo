# ADR0072. Extract optional apps and qualify an owned source transition

Accepted8 November2026 for AR-01..05. Extends ADR0071. No interoperability
with arbitrary Odoo addons is promised. Stock native UI remains the baseline.

## Source and dependency boundaries

Move the engine once to `engine/odoo`, launcher to `engine/odoo-bin`, framework
services to `framework_addons`, adopted apps to `applications`, examples to
`examples`, and useful native fixtures to `tests/addons`. Keep one source copy.
The image builder materializes the existing flat installed layout, so directory
ownership does not require unrelated runtime/serialized-ABI renaming. License
and source-origin notices survive moves and extraction.

Remove IAP and hosted editor media/text-generation features, including their
controls and routes. Local rich text, uploads, links and collaboration remain.
Move the generic link metadata helper into editor tools; messaging imports that
helper. Editor ICE discovery must work without messaging installed. Configured
optional communications providers are not equivalent to an Odoo cloud dependency.

Keep `mail` as an optional communication framework service: chatter, activities,
message history, notifications, shared conversation models/widgets and outgoing
delivery. Maintenance may depend on that service. Separate the full Discuss
workspace/client-action/menu/public-page entry points into an optional app and
POP/IMAP polling/model/configuration into another optional app. Shared widgets
and channel models need not be duplicated or moved merely because their original
names contain Discuss. The generic service must not activate unavailable app
actions. Tests must exercise notifications and record chatter without those apps.

Remove vendor application catalog/upsell/settings for absent modules. Available
module metadata comes from the actual distribution. Retain useful auth/import,
company, language, report, profiling and settings infrastructure; removing every
partner/company/currency model is a separate schema redesign, not this cleanup.

The audit found legacy RPC and HTTP-routing test helpers. Preserve useful
coverage by extracting test helpers or explicit test-only fixtures; do not adopt
their production applications just to satisfy historical test imports. Replace
the accounting-dependent main-flow fixture with a relevant owned-foundation
flow. Record exact final dispositions rather than claim every inherited test
remained unchanged.

## Populated deployments and authority

Core46 is immutable. Its independently verified kit/image/source is the baseline
for a new disposable Maintenance deployment. Observe installed modules and stored
records before removing source. Seed synthetic nonempty records to test actual
retention, not just empty-table deletion.

The existing ordinary core-upgrade guard remains strict. This cleanup needs an
explicit owned-release transition, with a private operator-reviewed declaration
bound into the staged plan. It binds exact source/target image and inventory,
policy and addon deltas, changed manifests/versions, migration code digest and
data/ownership effects. A package cannot grant this authority. Refuse unlisted
modules, arbitrary policy changes, stale declarations and changed source/target.
Do not embed a target image's digest inside its own build inputs.

For previously installed mail, preserve shared models and existing record IDs;
adopt extracted app records into their new owners using an enumerated XML-ID
ownership migration. Preserve previously available Discuss/gateway capabilities
through explicit app installation on that upgraded profile. Fresh Maintenance
gets only its declared communication dependency. Never silently discard saved
mailbox configuration, credentials, conversations, message history or attachments.

Retiring IAP requires an explicit archival/retirement step under old code before
its module disappears. Preserve populated business/configuration records in a
restricted recoverable representation and the independent checkpoint, record
counts/digests privately, then use supported module retirement. Do not simply
falsify installed-module state or leave a missing installed module at startup.
Archive secrets must remain private; public evidence contains counts/digests.

Pause/drain, current executor approval, claim fencing, independent checkpoint,
closed traffic on failure, fresh recovery and separately approved resume remain
mandatory. Recovery restores the exact old schema/data/image, including any
pre-transition retained data; unknown schema changes remain refused. If the
transition cannot satisfy these constraints, fix that protocol before proceeding.

## Freeze and qualification

Public plugin contracts remain at the existing106-file/8-row major1 freeze until
a concrete semantic change requires an explicit revision. Internal source paths
are not a reason to rename archived package paths. Any new operator descriptor
or plan fields need schema/validator/tests and a recorded freeze revision before
use; this ADR does not authorize accepting unvalidated fields.

AR-01 freezes these implementation boundaries, not a release pass. AR-02/03
must prove extraction/cold boot and actual source discovery; AR-04 proves the
specific populated transition and failure recovery; AR-05 independently verifies
final image reproduction, kit consumer, native UI, jobs, privacy and retirement.
Historical core46 evidence does not automatically qualify the changed release.
