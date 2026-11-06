# Stock WebClient release qualification

All five gates passed for the local `stock-r1` kit in `.local/releases/stock-r1`.
The release is bound to source `ad5ae338`, application image `07cacdf4`, and
the 54-component manifest `cf8c53b9`. The producer's kit stage is immutable.
The separate [qualification decision](../docs/evidence/G7/20261105-stock-release-repro/qualification-decision.json)
records acceptance for those exact bytes.

The local stock profile starts in Odoo's WebClient at `/odoo`. Notes uses native list and form actions with explicit workspace selection. The picker offers shortcuts for the release's reference plugins. The existing plugin host resolves authorized Canvas and platform tool routes at explicit `/app/` links. The release carries Notes, Notes Labels, Canvas and the Notes Stats connector and retains the independently configured document statistics worker. Aurora Tasks and upstream Maintenance stay in the separate stress profiles. The stock release therefore does not add IAP to its application image. Classify inherited Odoo links and exercise the supported workflows with outbound access restricted.

| Gate | Required evidence | State |
| --- | --- | --- |
| SW-01 | Declare entry point, plugin and worker scope. Prove workspace selection, safe reload and close behavior, and session-expiry recovery. §§16.3, 23.2, UI-03, UI-07, UI-10. | Passed. The selected build preserved the draft after canceling reload and close and displayed the session-expiry recovery action. |
| SW-02 | Build and independently reproduce the selected inventory, bind the exact kit to the source and validate its curated packages and notices. §§22, 28, BOOT-02, OPS-03. | Passed for `07cacdf4` and kit manifest `cf8c53b9`. Reproduced the declared application, compiler files under the worker memory limit and both Arabic catalogs. |
| SW-03 | Fresh install from the kit. Prove stock Notes, Labels, Canvas and the separate worker. Verify editor/viewer behavior and supported native UI paths. §§16, 27, UI-01, UI-02, SVC-01, SVC-05. | Passed on the exact fresh kit. Native editor and viewer forms, the Labels dialog, the one-card Canvas and the completed separate-worker result all passed. |
| SW-04 | Check the affected security, privacy, outbound, accessibility, RTL and performance boundaries on the selected release. §§17, 23.2, 24.1, SEC-02 through SEC-04, UI-09. | Passed. Native list and detail p95 were 367.832 ms and 169.833 ms with 10,000 notes and 20 concurrent sessions. |
| SW-05 | Verify an independently approved release transition, checkpoint restore and separate resume on populated disposable data. Record the exact qualification and retire disposable assets. §§13, 23, 28, OPS-02. | Passed. The approved transition preserved data and the completed worker job across the fault, fresh restore and separate resume. All five disposable sites were retired. |

The stock profile keeps inherited user-initiated links to Odoo Help and My
Odoo.com Account and the login attribution. The upstream administrator Apps
and Themes actions point to the Odoo catalog. The supported installer uses the
kit's curated archives and independent approval. The supported application
and job paths use local services. The locked RTL compiler is a local asset
tool. npm access is limited to dependency preparation. The application
reproduction and live checks run with outbound restrictions.

## Operator handoff

Use the existing [kit procedure](../docs/release-kit.md) with the stock
kit path and a fresh workdir. The independent runtime procedure is the same
for the stock profile. An internal fork release can use the same stock
dependency image until the compiler or its substrate changes. To rebuild the
dependency image, give `deploy/Dockerfile.stock-rtl` a temporary local tag
bound to the exact reviewed base image and use its npm lock. Then pass the
resulting immutable image ID and the stock policy to `tools/build_candidate.py`.
The candidate builder verifies the compiler version and the kit carries its
third-party notices.

Use the existing release producer, operator approval and reference tests where they cover the same boundary. Record live evidence separately from source tests. The completed R1 and shared foundation qualifications retain their original scope. Background execution expansion, R2, R3, and any production deployment are deferred.
