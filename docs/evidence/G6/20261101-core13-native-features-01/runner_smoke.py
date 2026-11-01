"""One installed original-actor read-only job through the normal operator CLI."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from run import ROOT,OUT,j,f,context,snapshot

state,native=context();assert f.load(j.LOCAL/'core13-feature-enable.json')['state']=='verified'
marker=j.LOCAL/'core13-feature-runner.json';assert not marker.exists()
before=snapshot(state,'core13-feature-runner-before');assert len(before['mp_job'])==18
assert all(r['state'] in ['completed','dead_letter','cancelled'] for r in before['mp_job'])
fixture=f.load(j.LOCAL/'fixtures.json');f.write(marker,dict(state='seeding'))
code='import json\nfrom uuid import uuid4\nfrom odoo import api\nfrom odoo.addons.mp_identity.scopes import scoped_environment\nfrom odoo.addons.mp_core.dispatch import CallFrame\nfrom odoo.addons.mp_core import job_dispatch as jobs\nFIXTURE='+repr(fixture)+'\n'
code+='native=scoped_environment(api.Environment(env.cr,FIXTURE["users"]["alice"]["id"],{}),FIXTURE["workspaces"]["C"]["public_id"])\nb=FIXTURE["bindings"]["C"]\nframe=CallFrame(FIXTURE["users"]["alice"]["principal_id"],b["workspace_id"],b["site_id"],b["consumer_installation_id"],"org.example.notes",())\nnative=native(context={**native.context,"_mp_call_frame":frame})\nnote=native["mp.example.note"].search([],limit=1);assert note\nident=jobs.enqueue_bound(native,"documents","org.example.notes:inspect_revision",dict(note_id=note.public_id,expected_revision=note.revision),uuid4().hex)\nvalue=dict(job_id=ident,note_id=note.public_id,revision=note.revision,user_id=native.uid)\nenv.cr.commit();print("MP_CORE13_JOB="+json.dumps(value))\n'
raw=f.command('core13-feature-runner-seed',['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','odoo-bin','shell',
    '-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0'],input=code.encode())
rows=[json.loads(l.split('=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_CORE13_JOB=')];assert len(rows)==1
seed=rows[0];f.write(marker,dict(state='seeded',**seed))
prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
args=prefix+['worker','--store',str(native.store.root),'--deployment-config',str(native.target_path),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
result=json.loads(f.command('core13-feature-runner-once',args,timeout=180))
after=snapshot(state,'core13-feature-runner-after')
for table in before:
    if table=='mp_job':continue
    assert before[table]==after[table],table+' changed during read-only job'
oldids={r['public_id'] for r in before['mp_job']};new=[r for r in after['mp_job'] if r['public_id'] not in oldids]
assert len(new)==1 and len(after['mp_job'])==19
job=new[0];assert job['public_id']==seed['job_id'] and job['state']=='completed' and job['attempts']==1
assert job['result']==dict(note_id=seed['note_id'],revision=seed['revision']) and not job['effect_started']
assert [r for r in after['mp_job'] if r['public_id'] in oldids]==before['mp_job']
principal=next(r for r in before['mp_principal'] if r['public_id']==fixture['users']['alice']['principal_id'])
assert job['actor_id']==principal['id'] and seed['user_id']==fixture['users']['alice']['id']
report=dict(result='passed_actual_installed_readonly_runner',image=native.config['image_id'],job_id=seed['job_id'],
    completed_once=True,original_actor=True,no_source_or_handler_substitution=True,normal_worker_operator_cli=True,
    all_business_authority_event_and_old_job_rows_exact=True,job_counts=dict(before=18,after=19),
    limits=['One read-only native job. No new lease/death experiment or external remote dispatch claim.'])
f.save('runner-smoke.json',report);f.write(marker,dict(state='completed',**report));f.phase(state,'core13_native_features_runner_verified');f.guard(state)
print(json.dumps(dict(result=report['result'],completed_once=True,original_actor=True)))
