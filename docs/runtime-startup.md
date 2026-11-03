# Runtime startup boundary

For a new environment, build/load the selected [locked proxy](proxy-build.md)
before using Compose. Its local immutable digest is independent of the app's
approved release/inventory; changing a template does not update running sites.
Use the explicit [selected operator interpreter](operator-toolchain.md); the
older local `.venv` is retained only as a checkpoint.

The current independent executor is the supported G5 lifecycle path. Read its private deployment configuration and journal rather than the historical bootstrap Compose file. Do not restart, initialize or seed an existing site to refresh its image.

New R1 images default to `/venv/bin/python /opt/modular/tools/start_worker.py -c /run/secrets/odoo_config`. Their operator-provided environment must include:

| Value | Independent source |
| --- | --- |
| `MP_EXPECTED_DATABASE` | Exact database in the approved private deployment/site configuration |
| `MP_EXPECTED_INVENTORY_DIGEST` | Exact inventory digest in the independently approved release lock |

Pin the immutable image ID, mount only the selected application configuration read-only and the selected data volume, and retain the managed profile's user/resource/network/read-only-root controls. An image's self-reported inventory is not an independent approval. Do not derive these values from the database or silently replace the published lock. The startup guard uses a read-only DB transaction; it never installs/upgrades/removes modules. Invalid startup must be reconciled through an exact independently reviewed lifecycle operation.

Native maintenance uses a separate explicit entrypoint selected by the independent executor after approval, traffic drain and checkpoint. Ordinary runtime accepts no maintenance arguments. An operator can explicitly bypass an entrypoint; this guard does not claim otherwise. Native plugins remain fully trusted code.

R0/G1 baseline images retain their baseline startup invocation. Historical R1 Compose/demo setup helpers predate publication/inventory pins and are not a complete clean-release installation procedure for new images. Do not disable the guard to reuse them. The supported fresh-install/publication procedure remains required G7 work; no current release or data was replaced by the startup qualification.

See [ADR0014](architecture-decisions/0014-default-runtime-startup.md), the [current status](implementation-status.md), and the [actual candidate/default startup evidence](evidence/G5/20261028T144000Z-default-startup/default-startup.json).

Platform-only images now have a separate independently prepared `deploy` operation under [ADR0015](architecture-decisions/0015-platform-image-deployment.md). Stage the exact image using the CLI, then nominate every existing installation/site/workspace with action `deploy`. Independently review the hash/source diff/checkpoint/native trust acknowledgement before apply. This changes release/inventory/epoch and replaces guarded workers; plugin package versions, native schema, permissions, bindings and availability stay fixed. It skips Odoo native maintenance. The app request API cannot propose/approve it, and a same-version plugin upgrade remains invalid. Current G5 generation15 includes the protected default entrypoint; managed workers retain the explicit host-qualified guard for compatibility with retained images. Native core Python/schema changes require a separate reviewed maintenance path; do not bypass this restriction.
