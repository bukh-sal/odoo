# ADR0089: reviewed native appearance reader

Status: accepted for provisional local qualification,15November2026.

The actual core0.2.13 appearance control sets the existing `color_scheme`
preference, but the native HTTP rendering context always returns light. Real
browser inspection confirms that selecting dark still loads `web.assets_web`.
The renderer already has a dark-asset branch; a second client-side theme engine
or forced CSS would duplicate that mechanism.

Modify the owned web `color_scheme()` reader directly: return dark only for the
exact `dark` cookie value, otherwise light. No authentication, session identity,
grant, database, route, asset URL or dependency declaration changes. The request
value never becomes an arbitrary bundle name. This is a presentation preference,
not an authority input.

The D04 maintenance path still rejects arbitrary web backend/model/controller
changes. Admit only the exact before/after full-file hashes of this reviewed
reader in the existing core-upgrade validator, with ordinary increasing native
versions, complete source diff, independent reconstruction, trust/destructive
acknowledgments, checkpoint and normal native maintenance. Every unrelated
backend edit, changed/unrecognized hash, removal and forged plan still refuses.
This is an attested source pair, not a new operator, recipe or executable hook.

Use a new unpublished core0.2.14/web19.0.2.14.0 identity. Preserve core0.2.13's
successful maintenance and failed appearance-check evidence; never relabel it.
Current app pins remain unchanged through this core correction. Browser proof
must show the actual dark stylesheet and native/custom computed colors, then
restore light through the normal control. Source tests alone cannot accept it.

This narrow exception does not promise general web-backend maintenance. A later
broader owned-core policy requires its own explicit review and qualification;
the exact attestation can then be retired without preserving a historical runner.
