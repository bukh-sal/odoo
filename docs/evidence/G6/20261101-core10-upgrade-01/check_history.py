"""Bounded independent read/rollback proof while pending identity fix is open."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f
state,record,native=context();assert state['phase']=='core10-history-01' and native.config['generation']==6
marker=j.LOCAL/'core10-history-01.json';assert f.load(marker)['state']=='running_rollback_only'
child=json.loads(subprocess.check_output(['docker','inspect',state['project']+'-core10-history-01']))[0];assert not child['State']['Running'] and child['State']['ExitCode']==1
assert json.loads(f.sql(state,'core10-history-rollback-01',"SELECT jsonb_build_array((SELECT count(*) FROM mp_event_subscription),(SELECT count(*) FROM mp_event_delivery),(SELECT generation FROM mp_dispatch_control),(SELECT count(*) FROM mp_job WHERE state='completed'));"))==[33,222,31,3]
f.save('history-attempt-01.json',dict(result='fixture_replay_result_assertion_corrected',diagnosis='Replay response contains delivery IDs, not producer event IDs; event_store.replay source127-139 and frozen protocol reviewed. Native old-release delivery/payload/ACK already passed before wrong assertion. Entire native transaction rolled back; exact retained subscription/delivery/control/completed-job counts confirmed. Resume corrected rollback-only probe, no runtime/build/install/job replay.',retained_original_source='history_native_attempt01.py'))
code='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nSEED='+repr(f.load(j.LOCAL/'core10-seed-01.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'+(OUT/'history_native.py').read_text()
raw=f.native(state,'core10-history-02',[],code);rows=[json.loads(l.split('MP_CORE10_HISTORY=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE10_HISTORY=')];assert len(rows)==1
f.save('history.json',dict(**rows[0],image_id=state['image_id'],inventory_digest=state['inventory_digest'],limits=['Installed native adapter proof; actual browser host facade/bus and versioned Notes batch fix still pending.','Pending native ORM identity-role flush defect remains open; this history case uses stable current committed authority and rolls back all fixture changes.']))
f.write(marker,dict(state='completed'));f.phase(state,'core10_history_qualified_identity_fix_required');f.guard(state)
print('Actual core10 retained event delivery/replay/foreign denial and native retained-tombstone dedup pass; identity flush fix remains required.')
