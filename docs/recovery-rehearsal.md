# Clean disposable recovery rehearsal

This is the G5 OPS-02 rehearsal procedure. The actual clean installation, committed native failure, fresh restore, separate resume and preservation checks passed on 29 October 2026; see [qualification](evidence/G5/20261029-clean-recovery-01/qualification.json). It uses the R1 single-host native recovery profile: the failed database and independent operator journal remain available for authoritative reconciliation. It does not claim recovery after losing every host/control/authority copy.

Use the repository's locked Python, exact retained image and curated artifacts. Keep all existing operated deployments intact. The fixture drivers below accept only their separately named `.local/g5-clean-recovery` environment and refuse an already attempted phase. They create a fresh PostgreSQL server, empty database/volumes, generated private credentials and new operator store. No prior database/filestore is copied. Native Python and same-origin code remain trusted; the network is internal and ingress is loopback only. No production integrations are configured.

Initial setup commands, once on a fresh checkout/environment:

```powershell
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_fixture.py configure
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_fixture.py initialize
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_fixture.py install
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_data.py seed
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_data.py board --workspace A
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_data.py board --workspace B
```

The first two commands explicitly initialize the trusted core. Reference packages then pass normal plan/register/independent exact-hash approval/apply; the fixture's private OS policy explicitly permits unattended disposable approval. Four Notes, labels, two one-card reference boards and one private native global attachment provide preservation checks. Notes/Canvas attachments remain excluded: no new attachment feature or Canvas product UI is introduced. Board creation uses ordinary scoped native RPC under the named actor; a completed marker is verified on repeat, and an uncertain create must be reconciled rather than retried.

Before fault injection, record the complete observed state, schema, business records, file hashes and old client/attachment/assets. Request one destructive Labels native uninstall under its own exact approval and checkpoint. The rehearsal driver will stop after its real native commit and before traffic, retaining `recovery_required`; it is an intentional fixture exception, not an OS-crash test. The failed database and original filestore remain intact. Record a later workspace-membership revocation in that failed source to prove the checkpoint cannot resurrect old authority.

For actual recovery, use the ordinary local CLI described in `operations.md`: inspect the journal, prepare restore, review the exact expiring decision/hash, restore into a fresh named DB with traffic closed, then separately prepare/review/resume. Select this fixture's private trust/control/catalog/target paths, not historical main-site examples. Never repair the journal by changing a failed operation to completed or copying app-side approval flags. A failed or interrupted restore requires marker/journal/child reconciliation before any next action; do not overwrite an existing restore database.

Verify exact reference records/schema/files/attachment bytes, previous executable image and artifact/dependency lock, a newer release epoch, retained failed DB/filestore, current revocations, rotated session secret, retired technical credentials and old client/plan fencing. Test native Odoo list/form/gateway and minimal Canvas get/save/conflict through the restored worker. Only then qualify OPS-02. Preserve diagnostics/checkpoints/images/volumes for inspection; no automatic cleanup or publication.

The remaining once-only steps on a newly configured disposable fixture are:

```powershell
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_auth.py
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_fault.py prepare
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_fault.py apply
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_restore.py kit
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_restore.py prepare-restore
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_restore.py restore
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_verify.py closed
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_restore.py prepare-resume
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_restore.py resume
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_http.py
.venv/Scripts/python.exe -X utf8 tools/clean_recovery_canvas.py
```

These drivers wrap the ordinary independently owned CLI; they do not bypass approval or repair journals. Review the captured exact decision and hash before each execution. The explicit unattended policy is restricted to this disposable rehearsal. Never replay these setup/fault/recovery commands against the already completed environment. Its marker is `restored_resumed`, generation4, operation `d53ed106-478b-4720-9c56-ff9b2dc946c9`; the original operation remains revoked.

The private recovery kit includes the coordinated DB/filestore checkpoint, exact image archive, curated artifacts and trust policy, independent control snapshot, host operator/contracts source, actual runtime/operator/tooling/build dependency locks and declarations, nonsecret configuration and separately protected secret inputs. Preserve the latest failed DB/current authority and control journal separately from the older checkpoint. Never substitute the historical control snapshot for current independent authority. The [final input audit](evidence/G5/20261029-clean-recovery-01/recovery-kit-final.json) supersedes the two incomplete fixture inventories; original diagnostics remain recorded.

The rehearsal changes Alice's password and a synthetic native user's password/TOTP/counter/groups/passkey after the checkpoint, then revokes Alice's B membership after the native failure. The host-only recovery adapter retains that current state through a private snapshot and public digest, clears remembered devices, rotates session secrets and revokes technical credentials. Unexpected native user/login/group footprints fail closed for explicit reconciliation. See [ADR0028](architecture-decisions/0028-native-authentication-recovery.md). No credential material belongs in public evidence or review output.

The Canvas step first proves the explicit workspace provisioning command verifies the same existing board without creating duplicates. It then advances each board from revision1 to2 with identical content, verifies same-key replay and stale-save conflict, and denies foreign-workspace IDs. Exact recovery comparisons happen before those two deliberate test saves. No Canvas API, product UI or styling is added; standard record screens use native Odoo list/form views.
