"""Once-only real recovered job effect, then native Odoo/HTTP checks."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from lifecycle import context,j,f,MARKER
import r1_probe
from modular_platform.dispatch_operator import DispatchMaintenance
state,config,native=context();assert state['phase']=='native_restored_resumed'
assert config['generation']==5
marker=j.LOCAL/'native-recovery-finish-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
fixture=f.load(j.LOCAL/'fixtures.json');seed=f.load(j.LOCAL/'native-recovery-seed-01.json')
code='FIXTURE='+repr(fixture)+'\nSEED='+repr(seed)+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'
raw=f.native(state,'native-recovery-before-runner-01',[],code+"PHASE='before'\n"+(OUT/'finish_native.py').read_text())
before=[json.loads(l.split('MP_NATIVE_RECOVERY_FINISHED=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_NATIVE_RECOVERY_FINISHED=')];assert len(before)==1
f.save('obsolete-tokens-and-retry.json',before[0])
f.write(marker,dict(state='running_guarded_runner',job_id=seed['job_id']))
args=['docker','run','--name',state['project']+'-native-recovery-real-runner-01','--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','768m','--pids-limit','128','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--env','MP_EXPECTED_DATABASE='+state['active_db'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],'--entrypoint','/venv/bin/python',state['image_id'],'-m','modular_platform.job_runner','--once']
raw=f.command('native-recovery-real-runner-01',args,timeout=120)
runner=[json.loads(l) for l in raw.decode().splitlines() if l.startswith('{')];assert runner==[dict(job_id=seed['job_id'],state='completed')]
f.save('guarded-runner.json',dict(result='passed_real_inventoried_runner_on_fresh_restored_database',output=runner[0],inventory_digest=state['inventory_digest'],image_id=state['image_id'],database=state['active_db'],source_injection=False))
f.write(marker,dict(state='guarded_runner_completed',job_id=seed['job_id']))
raw=f.native(state,'native-recovery-after-runner-01',[],code+"PHASE='after'\n"+(OUT/'finish_native.py').read_text())
rows=[json.loads(l.split('MP_NATIVE_RECOVERY_FINISHED=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_NATIVE_RECOVERY_FINISHED=')];assert len(rows)==1
f.save('resumed-native-job.json',rows[0]);f.write(marker,dict(state='native_effect_completed',job_id=seed['job_id']))
r1_probe.r1.r0.LOCAL=j.LOCAL;client=r1_probe.Client(state,fixture)
for workspace in ['A','B','C']:
    views=client.native('get_views',workspace=workspace,kwargs=dict(views=[[False,'list'],[False,'form']],options=dict(toolbar=False)))
    assert {'list','form'}<=set(views['views'])
note=client.call('get',dict(note_id=seed['note_id']),workspace='C');assert note['revision']==2 and note['title']=='Owned restored native job'
client.call('get',dict(note_id=seed['note_id']),workspace='A',expect=404,code='NOT_FOUND')
snapshot=DispatchMaintenance(native).inspect();assert snapshot['job_states']==dict(completed=2,dead_letter=2) and snapshot['control']['generation']==25 and snapshot['control']['state']=='enabled'
assert snapshot['tables']['mp_outbox']['rows']==34
assert snapshot['tables']['mp_event_consumption']['rows']==3 and snapshot['tables']['mp_event_consumer_state']['rows']==1
status=native.store.status(f.load(MARKER)['operation_id']);assert status['phase']=='restore_traffic_resumed' and status['traffic_resumed'] and status['state']=='revoked'
f.save('resumed-HTTP.json',dict(result='passed_native_views_and_scoped_record_after_separate_resume',native_Odoo_list_form=['A','B','C'],original_user_note_revision=2,foreign_workspace_denied=True,dispatch=snapshot,operation_status=status))
f.write(marker,dict(state='completed',job_id=seed['job_id']));f.phase(state,'native_recovery_qualified');f.guard(state)
print('Real recovered original-user job commits once at attempt2; old claim/receipt denied; native Odoo/scoped HTTP pass.')
