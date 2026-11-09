# 0060. Own the platform's release and upgrade path

Accepted 6 November 2026. Modular Platform remains a working name.

Odoo Community 19 is the fork's recorded starting point. The platform owns its core changes, version numbers, release cadence, supported plugin interfaces and database upgrade paths. Major upgrade qualification runs between supported releases of this platform. Following Odoo's major release sequence and migrating to future Odoo majors are outside the plan.

Review upstream changes periodically, with priority given to security fixes that affect retained code. For each selected fix, record the upstream reference, the affected fork code, how the change was adapted and the regression evidence. Keep the original baseline, license and attribution records. Qualify the resulting artifact as a platform release under the existing approval, provenance and recovery rules.

For a future breaking platform release, state which source releases and plugins are supported, which changes require migration and which public contracts need a new major. Prove the supported upgrade and recovery on populated disposable sites. The shared foundation rehearsal already provides a two-site procedure for a platform maintenance update. Original specification sections 10, 12, 15.4 and 27 and the remaining-check inventory are local-only (removed from the public tree).
