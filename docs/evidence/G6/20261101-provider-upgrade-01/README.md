# Actual same-worker metadata upgrade

`qualification.json` proves ordinary independently reviewed metadata upgrade
`ed313cfd-3e11-48a7-9651-7721847d2f87`, configuration12→13,
dispatch58→61. New immutable Document Stats0.1.1 raises its supported minimum
to platform0.1.13, where the metadata reader/executor is installed and qualified.
The curated0.1.0 archive and release history remain immutable.

The worker image and service contract are unchanged. Actual worker container,
start time/restart count, mounts/network, public key and independent publication
stay exact. The external installer does not start/stop/redeploy the remote service.
Host maintenance and worker replacement do occur in the checkpointed lifecycle;
the outstanding display correction must distinguish those two processes.

The enabled C feature remains enabled. Full native module rows, schema-column
signature, native artifact pins and release fields other than metadata pin,
generation/time are exact. All17 compared tables preserve original data/authority/
bindings/grants/events/job outcomes, allowing only the exact metadata version/
digest/manifest, feature timestamp, C policy increment and18 job epoch changes.
All19 previous job outcomes/inputs/attempts and46 checkpoint files are preserved.

`source-checks.json` records37 targeted planning/projection/staging checks and
the unchanged94-file/eight-row contract freeze. The new negative case rejects
the successor on platform0.1.12. Initial curation driver used a nonexistent
Catalog.get method and failed before trust/catalog/metadata changes; corrected
exact snapshot selection passed, with the failed observation retained privately.

`retire.py` archives diagnostics and removes only this completed operation's owned
terminal helpers/superseded host app; its exact result is in `retirement.json`.
An initial post-delete assertion compared the current short ID with full IDs;
the verification-only continuation corrects that comparison and checks archived
IDs are absent, without repeating deletion. No new image or volume is needed.
Active worker/public-only volume and current/checkpoint images are retained;
no global prune or unrelated deletion.

This is a same-worker-image metadata upgrade, not changed-image compatibility,
manager UI, installed connector/remote computation, suspension/unregistration,
outage/in-flight revocation or external recovery qualification. SVC04/05 and the
whole G6 gate remain open; acceptance and rough progress counts are unchanged.
