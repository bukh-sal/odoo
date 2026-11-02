# ADR 0036: one host-maintenance rule for operation previews

Date: 2026-11-02. Status: corrective G2 revision15 qualification.
Parent: F-01d, specification8.4/14.6/20.3; ADR0035.

Actual installed core14/shell10 browser preparation of a Document Stats-C
suspension failed with Validation failed. Reproduction from the real sanitized
profile/current metadata reached prepared_view, then the frozen semantic checker
raised Prepared restart description mismatch. The planner already correctly
marked checkpointed metadata maintenance as restarting host workers; the checker
duplicated the earlier native-only rule. Source routing tests had replaced the
save boundary and therefore missed the real public-preview validator.

Use one host_restart_required(plan) derivation in the SDK contracts module for
both planner display and prepared-view checking. External metadata operations
require host restart; checkpointed native enable/suspend does too, while retained
legacy short feature journals keep their backup-false/no-restart meaning. Native
install/upgrade/uninstall/remove/deploy preserve their existing restart behavior.
This says nothing about starting or stopping an independently managed service.
Do not change the plan hash, DTO shapes, OS approval or independent reader guards.

Revision15 records this semantic checker correction, the shared rule, boundary
regressions and this ADR. Every existing schema/example/golden remains unchanged;
no public API major or token change. New tests carry the actual controller's
prepared bundle through the real prepared_view for every metadata action and
reject false restart descriptions, while preserving native/legacy distinctions.
Core/SDK0.1.15 is required for a coherent immutable rollout; shell1.10 is unchanged.
No hot patch or source/image preflight bypass is permitted.

The failed browser request rolled back: actual app-request count stayed unchanged,
all17 business/authority/event/job tables and independent worker identity/publication
remain exact. An initial audit assumed a draft could persist before preview
validation; the actual zero-row result and existing HTTP rollback corrected that
hypothesis. No operation was submitted/imported/approved/applied, no credential or
endpoint changed and no cleanup/deletion is needed for the failed nomination.

Required return path: qualify revision15 and real-profile source reproduction,
build/admit/approve/activate one corrective core15 image, then retry the browser
nomination against that changed runtime and finish the same G6 lifecycle checks.
Native CRUD and Canvas remain unchanged. No whole SVC/G6 pass from source tests.
