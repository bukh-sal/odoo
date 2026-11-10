# Clean-core TEST candidate build

`deploy/distribution-r1-clean-probe.json` is a TEST-only selection: eight
framework addons, SDK and stock WebClient, with no reference or application
packages. It is not final framework selection or a code-pure release claim.

The clean materialization path (`tools/build_distribution.py` with
`"runtime_surface": "clean"`) copies only `packages/contracts/v1`, the selected
engine/addons, SDK, licenses/notices/requirements and the fixed
`tools/start_worker.py` entrypoint. It excludes host tools, reference operator,
project tests/fixtures and app/example/plugin/service source trees.

`deploy/Dockerfile` has a separate `clean-runtime` target. It starts from the
pinned Python image, copies only the builder `/venv` and `/release`, and adds the
existing pinned Node24.22.2/rtlcss4.3.0 compiler closure from
`deploy/stock-rtl` for stock WebClient. The legacy `runtime` stage remains the
default last stage. The clean target is selected explicitly; it does not inherit
a historical full runtime or remove source guards.

A future reviewed build must use the normal pinned Python/OS/npm
network-or-cache prerequisites. `--reproduction` and
`--dependency-base-image` are code-only maintenance modes and are rejected for
the clean policy. The build record identifies the clean target, source hashes,
RTL package-lock digest and expected Node/rtlcss versions; a successful image
build additionally verifies those versions and the locked stock-RTL notice
closure. Materialization and record tests do not prove all-layer image purity,
installed removal, native/UI qualification or deployment; those require a later
actual artifact/layer audit and separate qualification.
