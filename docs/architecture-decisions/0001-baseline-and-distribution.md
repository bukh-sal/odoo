# ADR 0001: exact upstream baseline and curated source distribution

Status: selected; runtime qualification pending G0. Date: 28 October 2026 (Asia/Riyadh).

Use the spec's official Odoo 19 commit as the Git ancestry on `platform/r1`. Preserve the complete checked-out upstream source and official remote; copy a curated distribution into the runtime image. The Git clone is shallow to avoid downloading unrelated history. The one later upstream commit inspected affects stock orderpoint horizons and does not justify changing the baseline. This review is not a complete vulnerability assessment.

Use digest-pinned Python 3.12.16 and PostgreSQL 16.15 images with Linux amd64. Freeze Python dependency resolution with hashes and use a dated Debian snapshot for OS build/runtime packages. Preserve the untouched requirements input and legal notices. Record actual image/build/dependency inventories after execution. Docker now exposes about 8 GB following the user's resource change.

Retain base/web, setup, TOTP/passkey/password-policy security, native import, bus, HTML editor and tour infrastructure. Omit external `rpc`, upstream native-addon upload, optional API documentation, IAP and Unsplash from the executable distribution, for the reasons in `deploy/distribution.json`. The full source remains in Git. Explicit server-wide load is `base,web`; password policy is explicitly installed, with other selected auto-install behavior measured in G0.

Alternative: ship all Community addons and rely only on addons-path. Rejected because core adds built-in paths and auto-install can introduce unwanted modules, native upload bypasses the planned executor, and optional integrations are unnecessary for local runtime independence. No security module is removed merely to reduce count.

Validation: current evidence proves source fetch and base image versions only. G0 must prove distribution integrity, login/assets, installed closure, native lifecycle, restore and multiworker behavior. Later vulnerability/license qualification remains required at G7. Revisit if a retained native feature needs an excluded dependency or a concrete security fix requires a new upstream baseline.
