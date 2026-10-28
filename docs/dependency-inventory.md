# Foundation dependency inventory

The executable allowlist is `deploy/distribution.json`; build verifies native manifest dependency closure without importing addons, materializes a fresh source tree and hashes its files into the image's `distribution-inventory.json`. All official source remains in Git, including excluded business addons. No ERP source is needed in the runtime distribution just to create catalog categories.

| Addon | Why retained | Installation behavior |
| --- | --- | --- |
| base | Native ORM, registry metadata, users, partners/company compatibility | Required native bootstrap |
| web | Standard HTTP sessions, assets, views/action client | Explicit initial install; server-wide load |
| base_setup | Settings/bootstrap support | Auto-install from base/web |
| auth_totp | TOTP security | Auto-install from web |
| auth_passkey | Passkey security and bundled WebAuthn implementation | Auto-install from base_setup/web |
| auth_password_policy | Password policy | Explicit initial install |
| base_import | Native import functionality; scope enforcement will be tested in R1 | Auto-install from web |
| bus | Native evented/web client plumbing | Auto-install from base/web |
| web_tour | Retained web tour/client infrastructure | Auto-install from web |
| mp_compat | Platform-owned SCSS contrast helpers otherwise supplied by optional editor | Auto-install from web |

The full upstream auto-install closure discovered by static inspection also includes `rpc`, `base_import_module`, `api_doc`, `html_editor`, `iap` and `web_unsplash`. Those are omitted from the executable distribution for explicit transport/install authority/optional integration reasons in the policy and ADR. TOTP/passkey/password-policy security is preserved. Server-wide load is explicitly `base,web`; tests must show external XML/JSON RPC routes omitted while retained web model transports still work.

`mp_r0_fixture` and `mp_r0_extension` are development-only lifecycle fixtures shipped in separate v1/v2/failing search paths in the R0 image. Only the selected variant is discoverable for a process; two versions are not loaded in one process. They are explicitly installed/uninstalled by the harness and are not part of the clean ten-addon baseline. Production release packaging must omit these fixture paths and enforce the R1 release inventory policy (BOOT-05).

The base Community data file includes commercial app catalog advertisements and OEEL license labels for those catalog rows. They are retained upstream metadata, not installed proprietary implementations. The installed-addon inventory and retained code license fields are the evidence for actual runtime content. Neutral discovery/catalog UX is later platform work.

Python direct inputs remain the pinned upstream `requirements.txt`. Linux/Python 3.12 resolution and all transitive artifact hashes are in `deploy/requirements-py312.lock`; separate pinned build requirements prevent unversioned source build backends. Actual package and OS inventories, runtime image identity and source hash manifest are recorded under the G0 evidence directory. Root LGPLv3/COPYRIGHT and notices within retained libraries/assets are preserved. Full vulnerability/SBOM/license qualification remains a required R1 release gate.
