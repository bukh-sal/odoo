"""Rollback-only candidate query discriminator; not installed/HTTP qualification."""
import importlib.util,json
from pathlib import Path
OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('notes8_profile_activation',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==28
image=f.load(OUT/'candidate-admission.json')['image_id']
before=m.snapshot(state,'notes8-profile-before');worker=m.worker(native,'notes8-profile-worker-before')
source=(OUT.parent/'20261102-performance-preflight-01/profile_reads.py').read_text()
code=source.split('code="""',1)[1].split('""".replace',1)[0].replace('FIXTURE',repr(f.load(m.j.LOCAL/'fixtures.json')))
code=code.replace('actual_installed_source=True','actual_candidate_source=True')
label='g7-notes8-profile-01'
argv=['docker','run','-i','--name',state['project']+'-'+label,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','1536m','--pids-limit','128',
 '--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--mount','type=volume,source='+state['project']+'_bootstrap,target=/run/mp-bootstrap,readonly','--entrypoint','/venv/bin/python',image,'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0']
raw=f.command(label,argv,input=code.encode(),timeout=300)
rows=[json.loads(line.split('MP_READ_PROFILE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_READ_PROFILE=')];assert len(rows)==1
assert m.snapshot(state,'notes8-profile-after')==before and m.worker(native,'notes8-profile-worker-after')==worker
f.save('candidate-query-profile.json',dict(result='candidate_discriminator_not_deployed',**rows[0],image=image,all17tables_worker_exact=True,limits='Single warm candidate shell; no HTTP/10k/performance-target claim. Candidate Notes8/Labels4; core/Canvas/Stats/worker unchanged.'))
print(json.dumps(rows[0]))
