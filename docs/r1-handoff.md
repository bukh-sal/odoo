# R1 local handoff

The local branch is `platform/r1`. The selected kit is
`.local/releases/r1-0.1.26`. Its `kit-inventory.json` records the exact source
commit, and `SHA256SUMS` identifies the manifest.
The status ledger identifies the active gate and the closure checklist tracks
the remaining §28 evidence. The kit is local and remains a draft while G7 is open.
[Implementation status](implementation-status.md) and [release checklist](r1-release-checklist.md)

## Start and verify a disposable installation

From the repository root, verify the selected kit with the pinned local Python.
Choose a fresh workdir and an unused loopback port before creating the operator
and running the catalog, application and worker steps.

```powershell
$python = '.local/toolchain/operator-python16/Scripts/python.exe'
$kit = '.local/releases/r1-0.1.26'
$work = '.local/release-kit-new-operator'
& $python -X utf8 release/verify.py $kit
& $python -X utf8 "$kit/scripts/setup_operator.py" $kit --workdir $work
& "$work/operator/Scripts/python.exe" -I "$work/source/tools/check_contract_freeze.py"
```

Use the exact reviewed catalog import and sequential `prepare`, `initialize`,
`install` and `check_reference.py` commands in the kit guide. Then run the
separate worker initializer and `connect_worker.py register`, `connect` and
`job` steps. The new reference's URL is recorded in
`$work/private/reference/state.json`. Fixture login names are in `fixtures.json`
and the generated credentials are in the adjacent protected
`account-passwords.json`. Keep those files private. The new-install commands
are for a separate workdir and target. [Release kit procedure](release-kit.md)

- [Shipped core26 reference](http://release-0afebf4f833b.localhost:18100) uses
  `.local/release-kit-rehearsal/private/reference`.
- [Fresh developer rehearsal](http://release-1c1f3b9c7a85.localhost:18101) uses
  `.local/release-kit-core26-rehearsal/private/reference`.

Standard Notes records open in Odoo list and form views. Notes Labels is the
native extension and Canvas is the minimal optional custom-page example. The
developer guide covers versioned example edits, reproducible packaging,
curation and independent native approval. Use the operation's independent
journal for its actual state and the recovery runbook for a failed fixture.
[Developer guide](developer-guide.md), [operations](operations.md),
[operator runbooks](operator-runbooks.md) and [recovery](recovery-rehearsal.md)

## Evidence and limits

- All 99 required acceptance checks passed. The contract freeze verifies
  106 files across eight rows. G1 records early feasibility and the status
  ledger maps all gates and acceptance IDs to evidence. The current backend audit
  matched every ID to the specification and checked all twelve runbook headings,
  fifteen CLI commands and the completed developer-upgrade journal.
  [Feasibility](evidence/G1/20261028t003753z/gate-G1.json),
  [contract freeze](contracts/freeze-v1.md), [work log](work-log.md),
  [evidence index](verification.md) and
  [backend audit](evidence/G7/20261105-section28-audit-01/backend-audit.json)
- The kit carries 52 verified components, 19 plugin archives, five images and
  13 wheels. Its selected core26 image has an independent no-cache runtime
  inventory reproduction. The provenance receipt binds upstream source, build
  inputs, runtime dependency inventory and notices. The source ZIP predates
  these final repository records.
  [Reproduction](evidence/G7/20261105-core26-repro-01/qualification.json),
  [provenance](evidence/G7/20261105-core26-release-kit-01/provenance.json),
  [source refresh](evidence/G7/20261105-core26-release-kit-01/source-refresh.json)
  and [upstream patch ledger](upstream-patches.md)
- The fresh core26 rehearsal passed scoped HTTP, native view descriptors,
  Labels, Canvas and separate worker execution. A dependency-changing fixture
  upgrade deliberately failed after its native commit and restored the previous
  release into a new database before a separately reviewed resume. The later
  core23 native uninstall fault separately exercised the changed executor and
  durable dispatch recovery. Both fault rehearsals retain their original scope.
  [Fresh backend](evidence/G7/20261105-core26-release-kit-01/fresh-backend.json),
  [failed upgrade and restore](evidence/G7/20261103-fresh-release-01/dependency-recovery/qualification-corrected.json),
  [uninstall fault and restore](evidence/G7/20261104-native-uninstall-recovery-01/qualification.json)
  and [recovery binding](evidence/G7/20261105-core26-release-kit-01/retained-recovery-binding.json)
- The fresh rehearsal then applied the independently reviewed Labels 0.2.5
  and Canvas 0.1.5 developer variants in four workspace scopes. Backend HTTP
  verified the modified Labels action, the served Canvas asset and scoped
  permissions, with business data and the separate worker preserved. This
  developer exercise uses its own image on port 18101. The release kit and
  reference on port 18100 retain the shipped variants. Fresh browser rendering
  is pending.
  [Review](evidence/G7/20261105-core26-developer-install-01/review.json) and
  [installed backend](evidence/G7/20261105-core26-developer-install-01/backend-verification.json)
- The fixture uses loopback ingress and an internal runtime network. Native
  Python and same-origin plugin code are trusted with their runtime authority.
  Independent operator review governs execution and grants constrain supported
  API paths. The reviewed dependency snapshot retains parser, codec and
  availability risks. The diagnostic and archive scans cover recorded
  detectors and known values. This handoff covers local disposable use.
  [HTTP security](http-security.md), [network](network-independence.md),
  [dependency inventory](dependency-inventory.md) and
  [final kit privacy](evidence/G7/20261105-core26-release-kit-01/privacy-delta-final.json)
