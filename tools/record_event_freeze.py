"""Record the reviewed additive revision13 inventory; qualification follows."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'docs/contracts/freeze-v1.json';freeze=json.loads(p.read_text())
assert freeze['revision']==12 and len(freeze['files'])==87
changed={name for name,old in freeze['files'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=old}
assert changed=={'packages/host_sdk/src/index.ts','packages/platform_sdk/modular_platform/contracts.py'}
added=['docs/architecture-decisions/0031-scoped-domain-event-delivery.md','docs/contracts/events-v1.md','packages/contracts/v1/event-transport.schema.json','packages/contracts/examples/v1/event-transport.json','packages/contracts/fixtures/v1/event-transport-cases.json','packages/host_sdk/tests/event_transport.ts','tests/test_event_contracts.py']
assert all(name not in freeze['files'] and (ROOT/name).is_file() for name in added)
freeze['contracts'].append(dict(name='scoped domain-event delivery',owner='F/G6',acceptance=['FREEZE-01','FREEZE-02','FREEZE-03','FREEZE-04','EVT-01','EVT-02','EVT-03','ID-03'],paths=added+sorted(changed),g1=['FEAS-01','FEAS-04']))
for name in added+sorted(changed):freeze['files'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
freeze['files']=dict(sorted(freeze['files'].items()));freeze['revision']=13
p.write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf8')

status=ROOT/'docs/implementation-status.md';lines=status.read_text().splitlines();now=datetime.now(timezone.utc).isoformat()
for i,line in enumerate(lines):
 if line.startswith('- Updated UTC:'):lines[i]='- Updated UTC: '+now
 elif line.startswith('- Active item:'):lines[i]='- Active item: **F-01b2: commit-safe scoped events and authorized delivery**. Its contract-freeze prerequisite is in progress: additive schema/protocol/types/fixtures under ADR0031, nine boundary tests passed. Requalify G2 revision13 before any runtime consumer. Existing G5/G6 runtimes unchanged.'
 elif line.startswith('**Overall roughly'):lines[i]='**Overall roughly83%; acceptance:84/99 passed,4 temporarily invalidated FREEZE checks,0 failed,11 not_run;5 R2 excluded.** Verified work is unchanged. G2 revision13 source qualification is pending; no event acceptance or progress credit from contract generation. JOB-01/02 remain qualified on retained runtime sources; G5 deployments unchanged.'
 elif line.startswith('| G2 |'):lines[i]='| G2 | B: contract freeze | invalidated | 10 | Revision12 retained; compatible additive revision13/94files under ADR0031 pending source/schema/types qualification. Runtime consumers must wait. |'
 elif line.startswith('| FREEZE-'):
  parts=line.split('|');assert parts[3].strip()=='passed';parts[3]=' invalidated ';parts[5]=' Compatible additive event DTO/protocol/types revision13 qualification pending; revision12 and old runtime evidence retained. ';lines[i]='|'.join(parts)
start=next(i for i,line in enumerate(lines) if line.startswith('## Blockers and limitations'))
target=next(i for i in range(start,len(lines)) if lines[i]=='| --- | --- | --- |')
lines.insert(target+1,'| G6-EVENT-FREEZE-01 | active prerequisite; source qualification pending | ADR0031 adds durable scoped subscribe/poll/ack/status/replay/close contract, minimized envelope and unchanged HostEvent facade. Nine boundary tests pass. G2rev13/94files must qualify before native/browser consumers; no deployment mutation. |')
capsule=next(i for i,line in enumerate(lines) if line=='## Resume capsule')
lines.insert(capsule+2,'- CURRENT F-01b2 contract prerequisite: previous turn PROGRESS (native JOB01/02,133e5dd8); clean tree and actual guarded app running/four job children terminal verified. ADR0031 chooses native bus wakeups plus durable current-authorized per-subscription receipts, no allocated-ID cursor, seven-day logical replay, one-hour subscription/15s ACK/five attempts/three replays, original-user deduped Labels projection. Additive schema/12 golden messages/types/protocol and nine boundary tests exist. G2rev13/94files temporarily invalidates FREEZE01..04 pending source qualification; runtime consumers not started, old sites unchanged. Reconcile qualification process/result before proceeding; no G6 event acceptance credit yet.')
status.write_text('\n'.join(lines)+'\n',encoding='utf8')
with (ROOT/'docs/work-log.md').open('a',encoding='utf8') as out:out.write('\n- '+now+' F-01b2 contract prerequisite started. Previous goal turn PROGRESS/133e5dd8, actual app live/four prior job children terminal and clean tree verified. Read status/ADR0029/0030/qualification/spec13/14/25.5F, native bus/transaction hooks/host facade/source. ADR0031 reuses native bus payload-free wakeups with durable per-subscription receipts rather than max allocated ID, current binding/scope authorization, bounded ACK/retry/replay and original-user native consumer effect dedup. Preserves HostEvent/nativeCRUD/Canvas. Added strict event transport schema/12goldens/protocol/exportedtypes/typefixture;9boundarytests pass authority-key rejection/coherent minimized payload/duplicates/calendar/byte-depth/number/retrybounds. Only two prior frozen sources changed (additive SDK validator and types);87→94files/7→8rows, revision13 recorded. FREEZE01..04/G2 temporarilyinvalidated pending qualification,84passed4invalidated11not_run,rough83unchanged. No runtime consumer/deployment/DB change. Return condition G2revision13 qualification pass before implementation.\n')
print(json.dumps(dict(revision=13,files=len(freeze['files']),rows=len(freeze['contracts']),qualification='pending')))
