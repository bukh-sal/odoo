# Verification evidence index

## G0 foundation: passed

Decision and source/runtime identity: [gate-G0.json](evidence/G0/20261027t234238z/gate-G0.json). Historical failed attempts are preserved in the same directory and explained in the work log. The corrected ten-addon baseline is the qualifying run.

| Observation | Evidence |
| --- | --- |
| empty database bootstrap | [20261028T000648534988Z-bootstrap.log](evidence/G0/20261027t234238z/20261028T000648534988Z-bootstrap.log) |
| login logout assets and anonymous controls | [20261028T001320256156Z-http-probe.json](evidence/G0/20261027t234238z/20261028T001320256156Z-http-probe.json) |
| native model and extension install | [20261028T001002968819Z-install.log](evidence/G0/20261027t234238z/20261028T001002968819Z-install.log) |
| schema upgrade | [20261028T001006972470Z-upgrade.log](evidence/G0/20261027t234238z/20261028T001006972470Z-upgrade.log) |
| upgrade values and attachment | [20261028T001009175718Z-check-v2.log](evidence/G0/20261027t234238z/20261028T001009175718Z-check-v2.log) |
| multiworker registry sync | [20261028T001254739829Z-http-probe.json](evidence/G0/20261027t234238z/20261028T001254739829Z-http-probe.json) |
| backup manifest | [20261028T001255951803Z-backup-manifest.json](evidence/G0/20261027t234238z/20261028T001255951803Z-backup-manifest.json) |
| committed fixture failure | [20261028T001259090266Z-fail.log](evidence/G0/20261027t234238z/20261028T001259090266Z-fail.log) |
| independent partial commit observation | [20261028T001301242499Z-check-partial.log](evidence/G0/20261027t234238z/20261028T001301242499Z-check-partial.log) |
| database restore | [20261028T001304374459Z-database-restore.log](evidence/G0/20261027t234238z/20261028T001304374459Z-database-restore.log) |
| filestore restore | [20261028T001307715558Z-filestore-restore.log](evidence/G0/20261027t234238z/20261028T001307715558Z-filestore-restore.log) |
| restored values and attachment | [20261028T001308501003Z-check-v2.log](evidence/G0/20261027t234238z/20261028T001308501003Z-check-v2.log) |
| destructive uninstall | [20261028T001310712599Z-uninstall.log](evidence/G0/20261027t234238z/20261028T001310712599Z-uninstall.log) |
| authority rotation and dependent states | [20261028T001313160348Z-reopen-authority-check.log](evidence/G0/20261027t234238z/20261028T001313160348Z-reopen-authority-check.log) |
| second build and fresh database | [20261028T001455995688Z-reproduction-summary.json](evidence/G0/20261027t234238z/20261028T001455995688Z-reproduction-summary.json) |
| two native registries | [20261028T001454086279Z-two-database-registry-proof.log](evidence/G0/20261027t234238z/20261028T001454086279Z-two-database-registry-proof.log) |
| styled login browser | [login-styled.jpg](evidence/G0/20261027t234238z/login-styled.jpg) |
| authenticated web client browser | [authenticated-webclient.jpg](evidence/G0/20261027t234238z/authenticated-webclient.jpg) |
| restored browser session denied | [restored-session-login.jpg](evidence/G0/20261027t234238z/restored-session-login.jpg) |
| source identity | [source-identity.json](evidence/G0/20261027t234238z/source-identity.json) |
| resource sample | [resource-snapshot.jsonl](evidence/G0/20261027t234238z/resource-snapshot.jsonl) |
| python inventory | [runtime-packages.txt](evidence/G0/20261027t234238z/runtime-packages.txt) |
| os inventory | [os-packages.txt](evidence/G0/20261027t234238z/os-packages.txt) |
| metadata regression | [metadata-regression.txt](evidence/G0/20261027t234238z/metadata-regression.txt) |

## Later gates

G2 contract freeze and G3-G7 R1 qualification are **not run**. R0 native observations do not certify those later boundaries. Five ISO checks are R2 exclusions. See the acceptance ledger for release status. Raw DB/filestore checkpoints and all generated passwords remain ignored local material, not tracked evidence.

## G1 feasibility: passed

Decision/source/environment: [gate-G1.json](evidence/G1/20261028t003753z/gate-G1.json). Backend command `python tools/g1_probe.py` passed 26 cases. Browser procedure: sign in as synthetic Alice; open A/B URLs in separate tabs; warm gateway/native views, try attributed write in B, refresh both deep links, exercise back/forward and route-only update, repeat native/custom transitions, delay an A callback then switch B, revoke Alice A from a separate maintenance process, observe cleared A and usable B, restore only that fixture, then select missing scope. Evidence [browser-proof.json](evidence/G1/20261028t003753z/browser-proof.json), linked screenshots and [source-identity.json](evidence/G1/20261028t003753z/source-identity.json). Qualified backend [report](evidence/G1/20261028t003753z/20261028T005744618594Z-backend-feasibility.json). Historical failed normalization attempts remain preserved.
