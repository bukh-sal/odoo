# Work log

## 2026-10-27T23:32:26.886278+00:00 / A-01 / environment and source initialization

Hypothesis: the available Docker Linux engine and managed Python are sufficient for isolated R0.
Actions: inspect tools and daemon; initialize Git branch `platform/r1`, add official upstream and fetch exact baseline.
Observed: Git 2.56.0, Docker Engine 29.9.2/Compose 5.6.1, Linux amd64, 16 logical CPUs, ~1.91 GiB Docker memory; Python 3.12.15/3.14.9 available via uv-managed paths. No existing Docker containers/images. Fetch succeeded; checkout pending.
New information: default Windows Python command is an alias, so use explicit interpreter; actual memory below benchmark profile is a measurement limitation, not yet a blocker.
Next: complete checkout, pin source/runtime, build baseline. No product acceptance has run.

## 2026-10-27T23:42:11.336118+00:00 / A-01 passed; A-02 in progress

Official checkout complete; exact baseline preserved as Git ancestry. Reviewed the one later 19.0 stock fix; baseline unchanged. Resolved 65 runtime dependencies with hashes; pinned build tools, base-image digests and dated Debian snapshot. Initial Docker build succeeded with pip check and a 4,486-file/10-addon curated distribution. Docker now exposes 8 GB after user allocation.

Changed: source/runtime locks, distribution builder/policy, Dockerfile/Compose and disposable lifecycle fixtures/harness. Source context was unnecessarily broad on the first build; restricted .dockerignore to curated inputs for subsequent builds. No app DB/filestore yet.

Next verification: rebuild current harness, initialize a fresh explicitly disposable database, then prove login/assets and installed closure. G0 is not yet passed.
