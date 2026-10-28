# Modular Platform

Implementation of [the specification](planning/modular_platform_spec.md) through R1 is in progress. The authoritative [checklist and resume record](docs/implementation-status.md) distinguishes implemented work, actual acceptance results and remaining gates. Upstream README/legal files remain intact.

G0-G4 are qualified: the local platform has workspace identity, a neutral shell, native Notes, the Labels extension and a custom Canvas page. G5 is in progress: [archive validation and the curated catalog](docs/packaging.md) are implemented; dependency planning, independent executor approval and recoverable lifecycle are next. Start with the [checklist](docs/implementation-status.md) and [baseline commands](docs/baseline.md). Jobs, the external worker and final release qualification remain G6/G7.

Do not publish this development profile, use production credentials/data, or treat native plugins as sandboxed. The local test harness owns only its generated disposable targets and keeps raw backup/credential material under ignored `.local/r0`.
