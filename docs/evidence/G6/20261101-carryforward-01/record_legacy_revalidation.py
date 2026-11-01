"""Bind observed targeted legacy tests/read-only runtime proof, retain G5 runs."""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert f.load(OUT/'legacy-profile.json')['result']=='passed_real_legacy_readonly_profile'
checks=[('test_restore_dispatch.py',11,'8a9d59'),('test_unchanged_recovery.py',10,'3abe0c'),('test_recovery.py',8,'ba48c9'),('test_native_auth_recovery.py',5,'2aeb03'),('test_executor_crash_fence.py',5,'8a1c9b'),('test_native_dispatch_resume.py',4,'186a1c')]
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
paths=['packages/platform_sdk/modular_platform/native_executor.py','packages/platform_sdk/modular_platform/restore_executor.py','packages/platform_sdk/modular_platform/unchanged_recovery.py','packages/platform_sdk/modular_platform/native_auth_recovery.py','packages/platform_sdk/modular_platform/recovery_reviews.py','packages/platform_sdk/modular_platform/operator_store.py']
record=dict(result='passed_legacy_host_revalidation',utc=datetime.now(timezone.utc).isoformat(),checks=[dict(file=name,passed=n,observed_tool_chunk=chunk,sha256=hashlib.sha256((ROOT/'tests'/name).read_bytes()).hexdigest()) for name,n,chunk in checks],tests=43,real_runtime='legacy-profile.json',frozen_files=94,protected_configuration_hashes=9,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},acceptance_revalidated=['MIG-01','MIG-06','MIG-08','MIG-09','OPS-02'],limits=['Revalidates the retained qualified G5 no-dispatch profile/default legacy branches; its completed install/fault/restore workflows are not replayed.','New native dispatch checkpoint/upgrade/recovery/resume branches remain unqualified G6 work despite passing kernel/source/control tests.','Native/HTTP/asset images and prior protected publication/data are unchanged; only the clean legacy DB was briefly restarted for exact read-only checks and returned stopped.'])
f.save('legacy-host-revalidation.json',record)
p=ROOT/'docs/implementation-status.md';value=p.read_text(encoding='utf8')
for ident in record['acceptance_revalidated']:
    old='| '+ident+' | E/G5 | invalidated |';assert old in value;value=value.replace(old,'| '+ident+' | E/G5 | passed |',1)
    lines=value.splitlines()
    for index,line in enumerate(lines):
        if line.startswith('| '+ident+' | E/G5 |'):lines[index]=line[:-1]+' Shared legacy host branch revalidated: carryforward-01/legacy-host-revalidation.json (43 tests + actual protected legacy SQL profile); native G6 extension still pending. |'
    value='\n'.join(lines)+'\n'
value=value.replace('| G5 | E: lifecycle and packaging | invalidated |','| G5 | E: lifecycle and packaging | passed |',1)
value=value.replace('**F / G6 in_progress; G5 shared host regression pending**','**F / G6 in_progress; G5 legacy profile revalidated**',1)
value=value.replace('G0/G1/G2rev13/G3/G4 passed. Historical G5-X01..X10/45checks qualified; five shared host-lifecycle checks temporarily invalidated while the queue-aware executor/recovery branches are integrated. No dependent gate qualification until their legacy branch is revalidated.','G0/G1/G2rev13/G3/G4/G5 passed for their retained profiles. G5-X01..X10/45checks qualified; five shared host cases revalidated under the current legacy branches (43 source tests and actual protected clean-DB SQL profile). Native populated-queue G6 extension remains unqualified.',1)
value=value.replace('**Implementation roughly84% before this source change; current verification estimate roughly81% while five shared G5 host cases await revalidation. Acceptance:83/99 passed,5 invalidated,0 failed,11 not_run;5 R2 excluded.**','**Overall roughly84%; acceptance:88/99 passed,0 invalidated,0 failed,11 not_run;5 R2 excluded.**',1)
p.write_text(value,encoding='utf8')
with (ROOT/'docs/work-log.md').open('a',encoding='utf8') as log:log.write('\n- '+record['utc']+' Shared G5 legacy host revalidation PASS:43 observed source cases (11effect/finalresume,10unchanged,8review/hash/store,5currentnativeauth,5lostowner,4newnativejournal/enable/latequeue orchestration). Exact protected cleanG5 DB restarted alone, legacy supported-effects false/zero and dispatchpresenceFalse/nochild verified; samegen4/config restoredstopped, no business/schema/files/user changes.94freeze/nineconfighashes exact. Retained original realG5 workflows bound; no mutation replay. MIG01/06/08/09/OPS02 restoredpassed/G5legacyrevalidated;88/99 andrough84. New native profile source integration still requires actual approved populated install/upgrade and reviewed recovery; no G6 pass.\n')
print('43 source checks + real legacy profile revalidate five shared G5 cases; G6 extension remains open.')
