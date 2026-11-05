# Stock WebClient release qualification

The local stock profile starts in Odoo's WebClient at `/odoo`. Notes uses native list and form actions with explicit workspace selection. The existing plugin host serves Canvas and platform tools at explicit `/app/` links. The release carries Notes, Notes Labels, Canvas and the Notes Stats connector and retains the independently configured document statistics worker. Aurora Tasks and upstream Maintenance stay in the separate stress profiles. The stock release therefore does not add IAP to its application image. Classify inherited Odoo links and exercise the supported workflows with outbound access restricted.

| Gate | Required evidence | State |
| --- | --- | --- |
| SW-01 | Declare entry point, plugin and worker scope. Prove workspace selection, safe reload and close behavior, and session-expiry recovery. | Active |
| SW-02 | Build and independently reproduce the selected inventory, bind the exact kit to the source and validate its curated packages and notices. | Pending |
| SW-03 | Fresh install from the kit. Prove stock Notes, Labels, Canvas and the separate worker. Verify editor/viewer behavior and supported native UI paths. | Pending |
| SW-04 | Check the affected security, privacy, outbound, accessibility, RTL and performance boundaries on the selected release. | Pending |
| SW-05 | Verify an independently approved release transition, checkpoint restore and separate resume on populated disposable data. Record the exact qualification and retire disposable assets. | Pending |

Use the existing release producer, operator approval and reference tests where they cover the same boundary. Record live evidence separately from source tests. The completed R1 and shared foundation qualifications retain their original scope. Background execution expansion, R2, R3, and any production deployment are deferred.
