"""Installed native authority matrix around a real computed remote invocation."""
import json,subprocess,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-notes-stats-remote-01'))
import remote as positive
context,base,f,j=positive.context,positive.base,positive.f,positive.j
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'installed-authority-01';MARKER=PRIVATE/'qualification.json'

WRAPPER='''import json,linecache,runpy,sys
def trace(frame,event,arg):
 if event=='line' and frame.f_code.co_name=='run_once' and frame.f_code.co_filename.endswith('/modular_platform/job_runner.py') and 'computed' in frame.f_locals and linecache.getline(frame.f_code.co_filename,frame.f_lineno).strip()=='with registry.cursor() as cr:':
  sys.settrace(None);frame.f_trace=None
  from odoo import api
  from odoo.addons.mp_core import job_dispatch as jobs
  registry=frame.f_locals['registry'];invocation=frame.f_locals['invocation'];computed=frame.f_locals['computed']
  cases=[('stats_grant','FORBIDDEN'),('documents_grant','FORBIDDEN'),('stats_binding','DEPENDENCY_UNAVAILABLE'),('documents_binding','DEPENDENCY_UNAVAILABLE'),('connector_feature','PLUGIN_SUSPENDED'),('provider_feature','PLUGIN_SUSPENDED'),('provider_registration','PLUGIN_SUSPENDED'),('actor_membership','FORBIDDEN')]
  results=[]
  for name,code in cases:
   with registry.cursor() as cr:
    try:
     env=api.Environment(cr,1,{})
     cr.execute('SELECT workspace_id,actor_id FROM mp_job WHERE public_id=%s',[invocation.claim.job_id]);workspace,actor=cr.fetchone()
     connector=env['mp.plugin.installation'].search([('plugin_id','=','org.example.notes_stats')]);provider=env['mp.plugin.installation'].search([('plugin_id','=','org.example.document_stats')])
     assert len(connector)==len(provider)==1
     if name.endswith('_grant'):
      capability='org.example.document_stats:analysis.run' if name=='stats_grant' else 'org.example.notes:notes.read'
      row=env['mp.plugin.grant'].search([('installation_id','=',connector.id),('workspace_id','=',workspace),('capability','=',capability)]);assert len(row)==1;row.write({'state':'revoked'})
     elif name.endswith('_binding'):
      row=env['mp.service.binding'].search([('consumer_id','=',connector.id),('workspace_id','=',workspace),('alias','=',name.split('_')[0])]);assert len(row)==1;row.write({'state':'unavailable'})
     elif name.endswith('_feature'):
      installation=connector if name=='connector_feature' else provider
      row=env['mp.workspace.plugin'].search([('installation_id','=',installation.id),('workspace_id','=',workspace)]);assert len(row)==1;row.write({'availability':'suspended'})
     elif name=='provider_registration':provider.write({'state':'removed'})
     elif name=='actor_membership':
      row=env['mp.membership'].search([('principal_id','=',actor),('workspace_id','=',workspace)]);assert len(row)==1;row.write({'state':'revoked'})
     result=jobs.finish_one(env,invocation,computed)
     assert result==dict(job_id=invocation.claim.job_id,state='dead_letter',error_code=code),(name,result)
     cr.execute('SELECT state,result,error_code FROM mp_job WHERE public_id=%s',[invocation.claim.job_id]);assert cr.fetchone()==('dead_letter',None,code)
     results.append(dict(name=name,error_code=code,rolled_back=True))
    finally:cr.rollback()
  print('MP_INSTALLED_MATRIX='+json.dumps(dict(job_id=invocation.claim.job_id,cases=results,actual_remote_computed=True)),flush=True)
  return None
 return trace
sys.argv=['modular_platform.job_runner','--once'];sys.settrace(trace);runpy.run_module('modular_platform.job_runner',run_name='__main__')
'''

def run():
    state,native=context();assert native.config['generation']==18 and not PRIVATE.exists();protect_directory(PRIVATE)
    before=base.snapshot(state,'installed-authority-before');worker=base.worker(native,'installed-authority-worker-before')
    assert len(before['mp_job'])==25 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
    record=f.load(j.LOCAL/'notes-stats-remote-01/positive.json');f.write(PRIVATE/'data-before.json',before);f.write(PRIVATE/'worker-before.json',worker)
    marker=dict(state='enqueuing');f.write(MARKER,marker)
    response=positive.call(positive.client(state),record,'analyze',dict(note_id=record['note_id'],expected_revision=record['revision']),'installed-matrix-'+uuid4().hex)
    assert response['job']['state']=='pending';job=response['job']['id'];marker.update(state='enqueued',job_id=job);f.write(MARKER,marker)
    op=WorkerOperator(native.store,native.target_path,j.LOCAL/'operator/worker-target.json');op.publisher._authorize()
    arguments=op._job_arguments(native.observer.read()['runtime'],str(uuid4()));assert arguments[-3:]==['-m','modular_platform.job_runner','--once'];arguments[-3:]=['-c',WRAPPER]
    marker.update(state='running_installed_matrix',container=arguments[arguments.index('--name')+1]);f.write(MARKER,marker)
    raw=f.command('installed-authority-run',arguments,timeout=150).decode()
    marker['state']='runner_terminal_needs_verification';f.write(MARKER,marker)
    rows=[json.loads(line.split('MP_INSTALLED_MATRIX=',1)[1]) for line in raw.splitlines() if line.startswith('MP_INSTALLED_MATRIX=')]
    assert len(rows)==1 and rows[0]['job_id']==job and len(rows[0]['cases'])==8
    outcome=next(json.loads(line) for line in raw.splitlines() if line.startswith('{') and json.loads(line).get('job_id')==job)
    assert outcome==dict(job_id=job,state='completed'),outcome
    status=positive.call(positive.client(state),record,'status',dict(note_id=record['note_id']))['job']
    assert status['id']==job and status['state']=='completed' and status['attempts']==1 and status['error_code'] is None
    assert status['result']==dict(note_id=record['note_id'],revision=record['revision'],statistics=record['expected_statistics'])
    after=base.snapshot(state,'installed-authority-after')
    for table in before:
        actual=[r for r in after[table] if r['public_id']!=job] if table=='mp_job' else after[table]
        assert actual==before[table],table
    assert base.worker(native,'installed-authority-worker-after')==worker
    assert not f.command('installed-authority-no-retained-runner',['docker','ps','--all','--filter','name=^/'+marker['container']+'$','--format','{{.ID}}']).strip()
    f.save('qualification.json',dict(result='passed_current_installed_authority_matrix_with_actual_remote_computation',source_commit='a7a00abf',configuration_generation=18,dispatch_generation=88,
        **rows[0],one_normal_completed_job_one_attempt=True,actual_native_startup_bridge_transport_and_finalize=True,
        test_only_trace_no_function_or_module_replacement=True,all8negative_case_writes_rolled_back=True,
        all_old25jobs_and_other16tables_exact=True,same_worker_and_publication=True,no_persistent_Docker_assets_added=True,
        limits=['Negative controls are same-transaction rollback fixtures, not committed manager lifecycle or independent publication changes. Committed actor/revision tests are separate. Technical credential/publication recovery and full lifecycle/image/browser checks remain.']))
    marker['state']='verified';f.write(MARKER,marker);f.phase(state,'installed_authority_verified');f.guard(state)
    print('Eight current installed native authority negatives reject real computed result; every negative rolled back, unchanged runner then completes once, old data/worker exact',flush=True)

if __name__=='__main__':run()
