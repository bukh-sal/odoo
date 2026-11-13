# Completed native checkpoint recovery

**Qualified for the bounded native PP04 B cohort.** The actual completed
uninstall/fresh restore/current-authority/bytes/continuation/separate resume/UI
[evidence](evidence/G7/20261113-pp04-completed-checkpoint-native-01/qualification.json)
supports the reviewed host source and exact retained runtime. It is not arbitrary
checkpoint or external-effect support. See
[ADR 0086](architecture-decisions/0086-independent-completed-checkpoint-recovery.md)
and [current status](implementation-status.md). Existing `plugin recover` remains
the separate failed-operation workflow.

This is point-in-time restoration after the exact current completed destructive
native uninstall, not undo of arbitrary external effects. It retains the current
database/filestore, restores a fresh namespace and preserves the original
operation's completed history. Current platform/native-login/grant authority is
reconciled; app business data and app-owned ACLs have checkpoint semantics.
Unknown effects, later deployments or an incompatible retained image refuse.
Grants revoked by a normal uninstall remain revoked after restoration; restoring
the old app data does not independently approve that integration again. A later
grant decision requires the normal independently reviewed operator workflow.

The PP05 correction also proves a fresh normal one-pass restore using distinct
source/restored fence children under the same real review. A retained partial
before the first restored fence has a narrowly reviewed continuation only for
the exact daemon name collision described in
[ADR0087](architecture-decisions/0087-reviewed-unstarted-restored-fence-continuation.md).
Unknown partials still refuse; never delete a child or repeat dump/extraction/
authority overlay. A successful command that misses a declared timing budget is
recorded as completed but is not a performance pass.

Source removal can preserve inactive same-image native recovery sources only
after the host independently proves their protected resumed history, inert
metadata and stopped workers/no clients. Unknown databases still block removal.
See [ADR0088](architecture-decisions/0088-proved-inactive-recovery-sources-during-removal.md).
Retained DBs/images/checkpoints are not physical erasure or an all-host purity claim.

Use the explicitly installed project interpreter and your protected operator
paths. `$sourceOperation` names the completed uninstall; `$recoveryId` is the new
identity returned by prepare. Keep decisions and diagnostics private.

```powershell
$python = '.\.local\toolchain\operator-python16\Scripts\python.exe'
$proposal = (& $python -I tools/modular.py --config $trust plugin checkpoint prepare-restore $sourceOperation --store $control --deployment-config $target --catalog $catalog) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Preparation refused; inspect before continuing' }
$recoveryId = $proposal.decision.operation_id
$proposal.decision | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $decisionFile -Encoding utf8
# Review the complete decision and its exact hash before the separate command.
& $python -I tools/modular.py --config $trust plugin checkpoint restore $recoveryId --store $control --deployment-config $target --catalog $catalog --decision $decisionFile --decision-hash $proposal.decision_hash
```

Interactive exact-hash confirmation is the default. `--noninteractive` requires
the existing explicit independent OS policy; it never supplies an approval.
Stop on any nonzero exit. Inspect the journal and actual resources; never repeat
restore, the source apply, dump loading or authority overlay because stdout was
lost. The status route reads the independent journal, not a fabricated ordinary
operation row:

```powershell
& $python -I tools/modular.py --config $trust plugin checkpoint status $recoveryId --store $control --deployment-config $target --catalog $catalog
```

Only a verified quiesce before **any** destination-creation intent supports the
initial continuation path. `prepare-continue` produces a new expiring exact review;
`continue` consumes that saved decision/hash. Other partial states refuse and
remain for explicit reconciliation. Status records are not proof a process is
still running; inspect the exact child handles before action. Old reviews are
invalid after current target, authority or source changes.

At `restored_verified` ingress remains closed. Use `prepare-resume` with the
current protected target to obtain a distinct decision, save/review it, then use
`resume` with that exact decision/hash. The same common arguments apply. Ordinary
forward registration/approval/apply cannot bypass this separate resume while the
recovery is active or uncertain. A pending resume is not safe to repeat.
`revoke-review` revokes a specific saved review; it does not undo any effect.

Retain source and restored databases, filestores, original history, checkpoints,
decisions, command receipts and images until their exact disposition is reviewed.
No prefix sweep, implicit deletion or production use is part of this workflow.
