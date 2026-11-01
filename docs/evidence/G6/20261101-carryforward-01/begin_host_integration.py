"""Mark the five shared host-lifecycle cases for targeted legacy revalidation."""
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];p=ROOT/'docs/implementation-status.md';value=p.read_text(encoding='utf8')
for ident in ['MIG-01','MIG-06','MIG-08','MIG-09','OPS-02']:
    old='| '+ident+' | E/G5 | passed |';assert old in value;value=value.replace(old,'| '+ident+' | E/G5 | invalidated |',1)
value=value.replace('| G5 | E: lifecycle and packaging | passed |','| G5 | E: lifecycle and packaging | invalidated |',1)
value=value.replace('**F / G6 in_progress; G5 passed**','**F / G6 in_progress; G5 shared host regression pending**',1)
value=value.replace('G0/G1/G2rev13/G3/G4/G5 passed. **All G5-X01..X10 exit criteria passed;45/45 G5 acceptance checks.**','G0/G1/G2rev13/G3/G4 passed. Historical G5-X01..X10/45checks qualified; five shared host-lifecycle checks temporarily invalidated while the queue-aware executor/recovery branches are integrated. No dependent gate qualification until their legacy branch is revalidated.',1)
value=value.replace('**Overall roughly84%; acceptance:88/99 passed,0 invalidated,0 failed,11 not_run;5 R2 excluded.**','**Implementation roughly84% before this source change; current verification estimate roughly81% while five shared G5 host cases await revalidation. Acceptance:83/99 passed,5 invalidated,0 failed,11 not_run;5 R2 excluded.**',1)
stamp=datetime.now(timezone.utc).isoformat();a=value.index('- Updated UTC:');b=value.index('\n',a);value=value[:a]+'- Updated UTC: '+stamp+value[b:]
value=value.replace('- Active item: **F-01e1:', '- Active item: **F-01e1 (including shared G5 host-branch revalidation):',1)
p.write_text(value,encoding='utf8')
with (ROOT/'docs/work-log.md').open('a',encoding='utf8') as log:log.write('\n- '+stamp+' F01e1 host integration prerequisite: carry-forward13cases plus3native restore/enable guards and current positive regression pass; guarded OS old-image preview/no mutation and stale-enable refusal pass. Now modifying the existing NativeExecutor/RestoreExecutor/UnchangedReleaseRecovery shared branches; MIG01/06/08/09/OPS02 and G5 temporarilyinvalidated for targeted legacy/source revalidation.83passed5invalidated11not_run; provisional verification~81, previouslyverified implementation~84. No dependent qualification or actual lifecycle mutation until revalidated.\n')
print('Five shared host cases/G5 marked for legacy revalidation before dependent qualification.')
