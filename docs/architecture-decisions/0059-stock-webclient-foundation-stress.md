# 0059. Use the stock Odoo WebClient for the foundation stress test

Status: accepted for the post-R1 stress test. This extends the reuse-first decision in [ADR 0010](0010-reuse-first-frontend.md).

Two independently operated systems use the same versioned Odoo Community foundation. Each selects its own native business addons. Odoo supplies the application menu, navigation, actions, view hosting, record widgets, dialogs and notifications. The Aurora Tasks slice uses declarative Odoo list and form views. Maintenance runs the pinned upstream addon and its native dependencies. Application-specific pages remain possible through the existing plugin capability, with Canvas serving as its bounded reference.

The stock WebClient needs the same dataset release fence as the existing platform shell. The identity addon contributes a bootstrap token and attaches it to native dataset calls. Each page captures its explicit workspace selection from the URL and carries it through Odoo's router. Opening a different workspace starts a separate page. The server resolves workspace membership and checks the release on every dataset request. The client bypasses Odoo's RPC cache for those calls because its cache identity does not include workspace or release headers. This adapter adds no screens or visual changes.

Aurora list participation, Maintenance record rules and platform workspace membership are separate. Both sites use the existing scoped Notes fixture to prove isolation in the same WebClient session and to keep lifecycle approval bound to real installation scopes. The current operator contract requires at least one installation target, including for a core maintenance plan. Asset preparation selects the fixed stock bundle when the custom shell is absent and keeps the existing fixed shell bundle for deployments where it is installed.

The stress test qualifies a stock deployment shape alongside the accepted R1 reference. The scoped fixture demonstrates list/form reads and viewer denial. Existing Notes updates still require a revision-aware write caller. [Stress test checklist](../../planning/shared_foundation_stress_test.md)
