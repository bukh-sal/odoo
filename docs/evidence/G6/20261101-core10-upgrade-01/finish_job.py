"""Actual new-image inventoried runner, then installed adapter regression."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f,MARKER
state,record,native=context();assert state['phase']=='core10_upgrade_preserved' and record['state']=='upgrade_preserved_needs_job_history'
private=j.LOCAL/'core10-job-finish-01.json';assert not private.exists();f.write(private,dict(state='before_runner'))
seed=f.load(j.LOCAL/'core10-seed-01.json');prefix='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nSEED='+repr(seed)+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'
raw=f.native(state,'core10-before-runner-01',[],prefix+"PHASE='before'\n"+(OUT/'job_native.py').read_text())
before=[json.loads(l.split('MP_CORE10_JOB=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE10_JOB=')];assert len(before)==1;f.save('job-before-runner.json',before[0])
f.write(private,dict(state='running_guarded_runner',job_id=seed['job_id']))
args=['docker','run','--name',state['project']+'-core10-real-runner-01','--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','768m','--pids-limit','128','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--env','MP_EXPECTED_DATABASE='+state['active_db'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],'--entrypoint','/venv/bin/python',state['image_id'],'-m','modular_platform.job_runner','--once']
raw=f.command('core10-real-runner-01',args,timeout=120);rows=[json.loads(l) for l in raw.decode().splitlines() if l.startswith('{')];assert rows==[dict(job_id=seed['job_id'],state='completed')]
f.save('guarded-runner.json',dict(result='passed_real_core10_inventoried_runner',image_id=state['image_id'],inventory_digest=state['inventory_digest'],output=rows[0],source_substitution=False));f.write(private,dict(state='runner_completed_needs_probe',job_id=seed['job_id']))
raw=f.native(state,'core10-after-runner-01',[],prefix+"PHASE='after'\n"+(OUT/'job_native.py').read_text())
after=[json.loads(l.split('MP_CORE10_JOB=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE10_JOB=')];assert len(after)==1;f.save('job-after-runner.json',after[0])
f.write(private,dict(state='completed',job_id=seed['job_id']));record['state']='job_qualified_needs_history';f.write(MARKER,record);f.phase(state,'core10_job_qualified');f.guard(state)
print('Actual new-image runner/original-user effect and completed semantic retry/current-role/no-reservation regressions pass.')
