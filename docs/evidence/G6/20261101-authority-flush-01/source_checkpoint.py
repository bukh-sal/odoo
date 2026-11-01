"""Bind distinct source cases without hiding the corrected test assumption."""
import ast,base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from secret_scan import Scanner
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='identity12_source_verified'
first=f.load(OUT/'source-01.json');focused=f.load(OUT/'source-02.json')
assert first['tests']==18 and not first['failures'] and first['errors']==['native_pending_authority.PendingAuthorityTests.test_service_mapping_without_credential_has_no_human_fallback']
assert focused['successful'] and focused['tests']==1
def functions(path):
    tree=ast.parse(path.read_bytes());return {n.name:ast.dump(n,include_attributes=False) for node in tree.body if isinstance(node,ast.ClassDef) for n in node.body if isinstance(n,ast.FunctionDef)}
before,after=functions(OUT/'native_tests_attempt01.py'),functions(OUT/'native_tests.py')
assert sum(1 for name in before if name.startswith('test_') and name in after and before[name]==after[name])==17
prior=ast.parse(subprocess.check_output(['git','show','HEAD:platform_addons/mp_identity/scopes.py']))
current=ast.parse((ROOT/'platform_addons/mp_identity/scopes.py').read_bytes())
named=lambda tree:{n.name:n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
a,b=named(prior),named(current)
assert all(ast.dump(a[name],include_attributes=False)==ast.dump(b[name],include_attributes=False) for name in ['Scope','canonical_uuid','current_scope','scoped_environment'])
old=a['resolve_scope'];new=b['resolve_scope'];calls=[n for n in new.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and getattr(n.value.func,'id',None)=='_flush_identity_policy'];assert len(calls)==1
new.body.remove(calls[0]);assert ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
freeze=f.load(ROOT/'docs/contracts/freeze-v1.json');assert len(freeze['files'])==94 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
values={k:base64.b64decode(v) for k,v in f.load(ROOT/'.local/g5-secret-scan/known-values.json').items()}
for folder in [j.LOCAL,ROOT/'.local/g6-jobs-runner',ROOT/'.local/g6-jobs',ROOT/'.local/g6',ROOT/'.local/g5-clean-recovery']:
    for path in folder.iterdir():
        if path.is_file() and path.name.endswith(('password','secret')) and len(path.read_bytes().strip())>=16:values[folder.name+'/'+path.name]=path.read_bytes().strip()
scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0');paths=[ROOT/p.decode() for p in names if p and (ROOT/p.decode()).is_file()]
findings=[hit for path in paths for hit in scanner.inspect_file(path,path.relative_to(ROOT).as_posix())];f.write(j.LOCAL/'identity12-source-private-findings.json',findings);assert not findings
for path in paths:
    if path.suffix=='.py':ast.parse(path.read_bytes())
    if path.suffix=='.json':json.loads(path.read_bytes())
record=dict(result='passed_18_distinct_native_source_cases',utc=datetime.now(timezone.utc).isoformat(),successful_cases=18,retained_unchanged_first_attempt_cases=17,focused_corrected_fixture_case=1,evidence=['source-01.json','source-02.json'],original_test_assumption='Core deliberately makes principal kind/user/public ID immutable; corrected test asserts that denial and an existing uncredentialed service identity cannot inherit human authority. No runtime policy was weakened.',scope_type_and_existing_SQL_and_cache_logic_AST_exact=True,change='One policy-only native ORM flush before original constrained SQL scope query; identity1.2.',source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'platform_addons/mp_identity/scopes.py',ROOT/'platform_addons/mp_identity/__manifest__.py',OUT/'native_tests.py']},frozen_files=94,protected_configurations=9,privacy=dict(files=len(paths),known_values=len(values),findings=0),limits=['Actual immutable identity1.2/native HTTP/two-worker/technical requalification still required;10acceptances/G1/G3 remain invalidated.','No core10 apply/job/producer replay, business write or authority change committed by source tests.'],next_action='Commit reviewed source/evidence, create new owned identity1.2 worktree from that HEAD retaining exact12 Notes0.2.6 inputs, initialize its owned private build lock before existing builder, strict validate identity-only native change, then independent corrective core upgrade and actual source/HTTP/worker qualification.')
f.save('source-checkpoint.json',record)
p=ROOT/'docs/implementation-status.md';s=p.read_text(encoding='utf8');s=s.replace('**F / G6 in_progress; G5 legacy profile revalidated**','**F / G6 in_progress; G1/G3 identity-source revalidation active; G5 retained profile passed**',1);s=s.replace('G0/G1/G2rev13/G3/G4/G5 passed for retained profiles;','G0/G2rev13/G4/G5 retain passed profiles; G1/G3 temporarilyinvalidated for the identity1.2 source change;',1)
lines=s.splitlines()
for n,line in enumerate(lines):
    if line.startswith('- Updated UTC:'):lines[n]='- Updated UTC: '+record['utc']
    if line.startswith('- Active item:'):lines[n]='- Active item: **F-01e1/ADR0033: immutable identity1.2 corrective upgrade/requalification**. Policy-only scope flush source passes18 distinct real native cases (17retained+1corrected immutable-mapping fixture); original Scope/cache/SQL logic AST exact except one flush call. Core10 upgrade/runner/history already executed and retained; do not replay. Next commit source/evidence, new owned isolated identity1.2 build retaining Notes.6, exact review/upgrade and installed native/HTTP/two-worker checks to restore10checks/G1/G3. No dependent gate pass from source tests alone.'
    if line.startswith('- NEXT sole item F-01e1:'):lines[n]='- NEXT sole item F-01e1/ADR0033: source-checkpoint18native cases passed; commit current source/evidence then create NEW owned .local/worktrees/g6-identity12 (codex/g6-identity12) at that commit. Restore only exact12 Notes.6 inputs from5daaf201, initialize private .local/operator/control/locks BEFORE existing build_candidate. Core/Shell/SDK stay1.10/1.9/.10; strict diff must show ONLY identity1.1→1.2 native maintenance/alloldpluginartifacts. Use normal stage/plan/review/approve/core_upgrade on current bac0/config6/freshDB, no new job seed needed: original5terminaljobs/25Notes/36events preserved and completed-key/pending-authority regression exercised by installed18case matrix plus actual HTTP/asymmetric/two-worker/technical checks. Restore10acceptances/G1/G3 before dependent qualification. Then Notes.7 separate upgrade/nativebatch/host-bus-browser/external/fullR1. Core10job e4288de6 and opd2185bf6 are terminal; no replay.'
p.write_text('\n'.join(lines)+'\n',encoding='utf8')
with (ROOT/'docs/work-log.md').open('a',encoding='utf8') as log:log.write('\n- '+record['utc']+' ADR0033 source prerequisite PASS:18distinct realnative cases (17firstsource run+1focused correctedfixture), currentpending role/member/principal/user/workspace/feature/policygen/credentialstate-expiry-audience-workspace-actions allhonored; cached originalScope/asymmetric/forgedcontext/actor/servicenoadmin and completedretry preserved. Initialone test tried core-immutable principal kind change; sourceconfirmedcorrect denial, correctedtest testsimmutability+existingworkercredentialabsence. No runtime editbetween17retained/1focused. OriginalScope/cache/function bodies/SQL AST unchanged exceptone metadataflush call;94freeze/nineconfigs/publicprivacy clean.10acceptances/G1/G3 remaininvalid untilactual immutable/nativeHTTP/twoworker requalification. Commitcheckpoint next, then newidentity1.2 core-only worktree retainingexactNotes.6, lockdirectory initializedbeforebuilder. No data/authority/job/apply replay; core10current5jobs3complete2DL/25Notes36events/control31 retained.\n')
print('18 distinct native source cases/AST/freeze/privacy verified; actual identity1.2 image/requalification still required.')
