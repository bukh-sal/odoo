# Application adoption delivery

AP-01..04 are complete: **100 verified weighted points,16/16 acceptance checks**.
[Final decision](evidence/post-r1/application-adoption/final-delivery.json),
[current status](implementation-status.md) and
[developer/usage limitations](application-adoption-limitations.md) identify the
exact scope. This is a local development release with fictional data.

| Phase | Completed result |
| --- | --- |
| AP-01 | Native Tasks daily pilot,roles/concurrency/reminder outage checks;ownership defaults repaired in immutable0.2.3 |
| AP-02 | Independent Tasks authoring/release established;actual populated Tasks-only update/fault/fresh original restore/current auth/separate resume/effects on unchanged foundation |
| AP-03 | Independently authored Projects and optional Tasks links;both-resource authority,new target date,populated app-set upgrade/recovery;debug denial disclosure repaired in immutable extension0.1.1 |
| AP-04 | Portable Git bundles/recipes,updated offline host operator,clean source/package/inventory reproduction,routed CLI install/planned stop-restart,finite credential audit and owned cleanup |

## Delivered bytes and source

Kit:`.local/releases/foundation49-application-adoption`.
Its57components verify with `scripts/verify.py`;manifest SHA-256:
`07bf94533a487fc56aa48b5fefc26d79718a50b02a9801825a7cf1a94f598eb6`.
The dated source snapshot is commit
`0927861b195300651d1ddcb75f22b002ef35633b`;this final decision separately qualifies
the clean workflow against those immutable bytes. Source-archived status pages
are dated pre-qualification records,not the current live checklist.

| Independent application | Final version | Source commit | Archive SHA-256 |
| --- | --- | --- | --- |
| Tasks |0.2.3|`db32b467fb46156254e481900c0461430888b703`|`e407fb631893410bc4ddc72b2548ad0cdb7336614da6f5abc17ff7f812fd1a83`|
| Projects |0.1.1|`1d801d6084b0004b4c7573f92b9447bd68406ef1`|`545fa0221612c9a89f663e08c77c921a0fc7553aa5877195dfcb5f373ca0dbf8`|
| Optional Projects–Tasks integration |0.1.1|`a79ed6049b21151bdafdb42966059d1da2852298`|`14d69ee24f8e54636be72b9e65c02767dfb196c555bce0c99cf89357abc73ccf`|

Each app is in its own source repository under
`.local/application-adoption/apps`;portable Git bundles in the kit preserve both
the final source and baseline history. Six final/baseline archives reproduced
exactly from clean downstream clones. Final composition preserves the same
file/native/package inventory:
`sha256:fc709b8441498cec3135f2802dd31b6c60d128e1db33600981362a8a0a6fa7ea`.
OCI image construction metadata may differ on recomposition;staging/approval
always pins the actual immutable image ID.

The delivered native image is
`sha256:b0920ae4d434bb96ddc874dc602676477836b8e61435ab7e9e4cc78fde1f907d`,
on unchanged foundation0.1.49. Sealed49/47/46 manifests/images remain preserved.
Use this kit's updated independent host operator for native-job recovery;
ADR0079 is a host correction,not a modification of those sealed runtimes.

## Use the pilot and develop another application

Primary pilot:[native Projects and Tasks](http://release-8a22293a20e7.localhost:18178/odoo).
The retained in-app tab shows active Project1 with target date15November2026,
current roles and a native linked Task. Alice's fictional login is`at_alice`.
Generated credentials/current operator target are private under:

`.local/application-adoption/clean-operator-01/source/.local/application-adoption/ap04-clean-01`.

The independent [Tasks pilot](http://release-261d5d0954ee.localhost:18172/odoo)
remains useful. [Pilot inventory/start-stop](application-pilot.md),
[developer path](application-development.md) and
[explicit operator lifecycle](application-operations.md) give the commands.
There are two intentional pilots,total10running containers/12volumes/4networks;
each has1urgent+1bulk lane and no producer. Review retention before the next app
or foundation release;retire exact owned resources when a pilot is superseded.

Final cleanup removed35stopped helpers,four unused app images and eight redundant
retention tags. The Projects-only and fault/recovery siblings were retired
separately. Recovery baseline images remain in the checksummed kit archive and
can be loaded when needed. Private logs/checkpoints remain;unrelated Docker assets
were not pruned.

## Qualification and remaining boundaries

The clean isolated host run passed88of89cases with one Windows symlink-privilege
skip. Actual native installation,seven integration groups,debug-error denial,
bounded fleet review and planned same-release stop/restart passed. Earlier real
fault/restore/separate-resume proofs preserve original project/task/link/role/file
data,current native authentication revocation and actual once-only reminder
effects;revoked-origin work stays held. The finite delivery audit found no
matches for60generated credential values across14138source files,103archive
members,43app files and56app-history blobs. Its scope is explicit in the receipt.

Remaining limits include native text last-save-wins,inbox-only bounded reminders,
the Queued summary for held reminder jobs,checkpoint semantics for application
role rows,initial exact compatibility bounds and a local qualification bootstrap
without a production provisioning wizard. Generic post-checkpoint application-ACL
overlay,full Aurora import/CRM/accounting,hostile-code isolation and visual redesign
remain outside this delivery. Agent walkthroughs are not human usability signoff.
The limitations register keeps each observed defect,fix and deferred trigger.
