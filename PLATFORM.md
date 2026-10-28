# Modular Platform

Implementation of [the specification](planning/modular_platform_spec.md) through R1 is in progress. The authoritative [checklist and resume record](docs/implementation-status.md) distinguishes implemented work, actual acceptance results and remaining gates. Upstream README/legal files remain intact.

The current runnable slice is the Odoo Community foundation, not the finished neutral platform. Start with [baseline commands and observed behavior](docs/baseline.md). R1 workspace/identity contracts, shell, plugin distribution, executor and reference applications follow the explicit G1/G2 and later gates.

Do not publish this development profile, use production credentials/data, or treat native plugins as sandboxed. The local test harness owns only its generated disposable targets and keeps raw backup/credential material under ignored `.local/r0`.
