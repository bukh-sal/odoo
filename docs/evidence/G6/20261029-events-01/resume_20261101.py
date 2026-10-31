"""Reconcile terminal evidence and restart only the same owned stopped site."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
import fixture as j
f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state)
out=Path(__file__).resolve().parent
assert f.load(out/'native-technical-01.json')['successful']
assert f.load(j.LOCAL/'technical-01.json')['state']=='completed'
target=f.load(j.LOCAL/'operator/target.json')
names=[state['project']+'-db-1',target['worker_id'],state['project']+'-edge-1']
objects=json.loads(subprocess.check_output(['docker','inspect',*names]))
assert all((o['Name'].lstrip('/')==name or o['Id']==name) and o['State']['Status']=='exited' and o['State']['ExitCode']==0 for name,o in zip(names,objects))
assert objects[1]['Image']==state['image_id']
assert all(o['HostConfig']['LogConfig']['Type'] in {'none','local'} for o in objects)
assert all(o['Name'].startswith('/'+state['project']+'-') for o in objects)
child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-events-technical-01']))[0]
assert child['State']['Status']=='exited' and child['State']['ExitCode']==0
evidence=dict(result='terminal_success_reconciled',utc=datetime.now(timezone.utc).isoformat(),previous_goal_turn='progress',technical_test='native-technical-01.json',prior_native_tests=12,technical_tests=1,image_id=state['image_id'],containers=[dict(name=o['Name'],id=o['Id'],state=o['State']['Status'],exit_code=o['State']['ExitCode'],image=o['Image']) for n,o in zip(names,objects)],preflight_correction='Initial fixture assertion compared recorded worker ID to Docker name and stopped before mutation; reconciled exact full ID/name. Existing ordinary runtime local log driver preserved; transient native helpers use none.',action='Restart these exact stopped containers; no create, initialize, install, migration or reset',acceptance_credit=False)
f.save('resumption-20261101.json',evidence)
status=f.ROOT/'docs/implementation-status.md';text=status.read_text(encoding='utf8')
text=text.replace('- Updated UTC: 2026-10-29T15:49:15.511752+00:00','- Updated UTC: '+evidence['utc'])
start=text.index('- Active item:');end=text.index('- Current result:',start)
text=text[:start]+('- Active item: **F-01b2: commit-safe scoped events and authorized delivery**. G2revision13 passed/94files/eight rows/105 tests. Immutable event image a3376530/core1.9/Shell1.8/Notes0.2.6/Labels0.2.3 deployed once on owned g6events18088. Twelve committed native tests plus one scoped technical-credential case passed; actual frontend source tests12 passed. HTTP/browser/protected/privacy qualification remains before EVT acceptance. Current resumption reconciles terminal technical-01; restart same stopped DB/app/edge only.\n')+text[end:]
text=text.replace('| F-01b2 | Commit-safe producer events, scoped delivery and deduplication | not_started | EVT-01..03 | F-01b1; additive public contract freeze first | Inspect current host-event facade/native bus, freeze new DTOs, then actual out-of-order commit/duplicate/revocation proof |','| F-01b2 | Commit-safe producer events, scoped delivery and deduplication | implemented_unverified | EVT-01..03 | F-01b1; G2rev13 passed | events-01/native-backend-01.json12 + native-technical-01.json1 pass; frontend-source-authority.json12. Binding epoch, HTTP/browser/protected/privacy checks remain; no EVT credit yet |')
a=text.index('- CURRENT F-01b2 runtime source');b=text.index('- Goal active through',a)
text=text[:a]+('- CURRENT F-01b2 event image a3376530/inventoryb81a4d69 on `.local/g6-events/state.json`, projectmp-r0-r1g64bb76636070f/DBmp_disposable_r0_r1_g6_4bb76636070f/site772b79cc-2d67-4fd5-a5b2-feadfd8db1aa/18088; generation2, own catalog9/trust4. Native init/install terminal, never replay. Core1.9/Shell1.8/Notes0.2.6/Labels0.2.3. Twelve real committed cases pass including inverse commit order, transactional effect/dedup/rollback, late/obsolete ACKs, retry/DL/replay and live revocation; technical-01 passed and child exited0. Twelve actual JS transport tests pass. Source checks55 and freeze94 pass. All rows retained/dispatch paused. Current Docker DB/app/edge found stopped exit0; restart exact containers, no create/reset. Then targeted binding-01, HTTP authentication/CSRF/release/private ACL/native views, browser facade, changed job origin regression, protected and privacy audits. Canvas unchanged/theme-only; use test harness for events, not a new product feature.\n')+text[b:]
a=text.index('- NEXT sole item F-01b2:');b=text.index('\n\n## Acceptance ledger',a)
text=text[:a]+('- NEXT sole item F-01b2: reconcile/restart exact event fixture, run only new targeted binding-epoch case, then actual HTTP/browser and protected/privacy checks. Original failed smoke/CLI evidence retained. Do not rerun completed12native/12JS or create another fixture. EVT01..03 remain not_run until source-bound qualification. F-01c external worker and F-01e actual populated-queue recovery remain required. Fix pending native revision defect through a versioned upgrade; standard CRUD native Odoo, Canvas minimal.\n')+text[b:]
status.write_text(text,encoding='utf8')
with (f.ROOT/'docs/work-log.md').open('a',encoding='utf8') as log:log.write('\n- '+evidence['utc']+' F01b2 resumption/direction checkpoint PROGRESS: previous turn implemented/deployed immutable a337 event source and verified12 committed native cases plus technical-01 scoped credential case (terminal child exit0 now reconciled). Actual12JS cases and55 source checks retained. Same owned DB/app/edge stopped clean exit0 across elapsed downtime; restart exact containers only, no create/init/install/migration/reset. Next binding epoch and actual HTTP/browser/protected/privacy. EVT acceptance remains unclaimed,88/99 andrough83 unchanged; pending-revision and populated-queue recovery remain required. resumption-20261101.json records exact identities.\n')
f.command('resume-20261101-db',['docker','start',names[0]])
ready=subprocess.run(['docker','exec',names[0],'pg_isready','-U','postgres'],capture_output=True)
assert ready.returncode==0,'Inspect same database readiness before starting app; do not recreate'
f.command('resume-20261101-app',['docker','start',names[1]])
f.wait_ready(names[1])
f.command('resume-20261101-edge',['docker','start',names[2]])
f.guard(state)
print(json.dumps(dict(result='same_owned_containers_restarted',project=state['project'])))
