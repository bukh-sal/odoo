"""Current installed runner, actual death/reclaim/revocation/error boundaries.

No runner/queue/authorization source substitution. Trace instrumentation only
pauses before compute/finalize, or replaces a registered compute callback to
exercise failures. Cancel delegates to the real installed bridge claim fence.
"""
import dataclasses,json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerOperator
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);fixture=f.load(j.LOCAL/'fixtures.json')
MARKER=j.LOCAL/'core11-runner-01.json';assert not MARKER.exists()
f.write(MARKER,dict(state='starting',image_id=state['image_id']))
store=OperatorStore(j.LOCAL/'operator/control');operator=WorkerOperator(store,j.LOCAL/'operator/target.json',j.LOCAL/'operator/worker-target.json')
native_base="""import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core import job_dispatch as jobs
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
b=FIXTURE['bindings']['C'];frame=CallFrame(FIXTURE['users']['alice']['principal_id'],b['workspace_id'],b['site_id'],b['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame})
"""
def native(label,code):
    raw=f.native(state,label,[],'FIXTURE='+repr(fixture)+'\n'+native_base+code)
    rows=[json.loads(line.split('MP_RUNNER=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_RUNNER=')];assert len(rows)==1
    return rows[0]
def snapshot(label,job):
    return json.loads(f.sql(state,label,"SELECT jsonb_build_object('state',j.state,'attempts',j.attempts,'generation',j.claim_generation,'error_code',j.error_code,'cancel_requested',j.cancel_requested,'result',j.result,'title',n.title,'revision',n.revision,'write_uid',n.write_uid,'lease_remaining',GREATEST(0,extract(epoch FROM j.lease_until-timezone('UTC',clock_timestamp())))) FROM mp_job j JOIN mp_example_note n ON n.public_id=j.payload->'input'->>'note_id' WHERE j.public_id='"+job['job_id']+"';"))
def seed(label,write):
    code=("note=native['mp.example.note'].create(dict(title='Installed   runner   '+uuid4().hex))\n" if write else "note=native['mp.example.note'].search([],limit=1);assert note\n")
    code+="ident=jobs.enqueue_bound(native,'documents',"+repr('org.example.notes:normalize_title' if write else 'org.example.notes:inspect_revision')+",dict(note_id=note.public_id,expected_revision=note.revision),uuid4().hex)\nvalue=dict(job_id=ident,note_id=note.public_id,title=note.title,revision=note.revision,user_id=native.uid)\nenv.cr.commit();print('MP_RUNNER='+json.dumps(value))"
    result=native(label,code);f.write(j.LOCAL/(label+'.json'),result);return result
def cli(label):
    args=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json'),'worker','--store',str(store.root),'--deployment-config',str(j.LOCAL/'operator/target.json'),'--worker-config',str(j.LOCAL/'operator/worker-target.json'),'run-job-once']
    return json.loads(f.command(label,args,timeout=180))
def create(label,mode):
    # Use the normal operator's actual image/database/inventory/mount selection.
    runtime=dict(inventory=dict(files={}),inventory_digest=state['inventory_digest'])
    from modular_platform.deployment import inspect_image
    runtime=inspect_image(state['image_id'])
    operation=str(uuid4());args=operator._job_arguments(runtime,operation)
    args.remove('--rm');args[1]='create'
    name=state['project']+'-'+label;args[args.index('--name')+1]=name
    args=args[:-3]
    wrapper="""import dataclasses,json,pathlib,runpy,sys,time
from dataclasses import replace
path='/opt/modular/packages/platform_sdk/modular_platform/job_runner.py'
lines=pathlib.Path(path).read_text().splitlines()
before=next(i for i,text in enumerate(lines,1) if text.strip()=='computed=jobs.compute(invocation)')
final=next(i for i,text in enumerate(lines,1) if text.strip().startswith('try:result=retrying(lambda:jobs.finish_one'))
mode=MODE
handled=False
def trace(frame,event,arg):
 global handled
 if handled or event!='line' or frame.f_code.co_filename!=path:return trace
 target=final if mode=='revoke' else before
 if frame.f_lineno!=target:return trace
 handled=True;invocation=frame.f_locals['invocation']
 if mode in ('kill','revoke'):
  print('MP_BARRIER='+json.dumps(dataclasses.asdict(invocation)),flush=True)
  deadline=time.monotonic()+60
  while not pathlib.Path('/tmp/fixture-resume').exists():
   if time.monotonic()>=deadline:raise RuntimeError('Fixture barrier deadline')
   time.sleep(0.1)
 else:
  from odoo.addons.mp_core import job_dispatch as jobs
  from modular_platform.worker_dispatch import WorkerDispatchError
  key=invocation.handler,invocation.version
  def fault(prepared,context):
   if mode=='unavailable':raise WorkerDispatchError('DEPENDENCY_UNAVAILABLE',sent=True)
   from odoo import api
   from odoo.modules.registry import Registry
   from modular_platform import durable
   from odoo.addons.mp_core.external_job import _snapshot,AUTHORITY_ROOT
   registry=Registry(context['_native_job']['database'])
   with registry.cursor() as cr:
    cr.execute('SELECT actor_id,workspace_id FROM mp_job WHERE public_id=%s',[context['job_id']]);actor,workspace=cr.fetchone()
    assert durable.cancel(cr,context['job_id'],actor_id=actor,workspace_id=workspace);cr.commit()
   # Real installed bridge fails its claim fence before endpoint lookup.
   return _snapshot(registry,context['_native_job'],prepared,context,'stats',AUTHORITY_ROOT)
  jobs.DEFINITIONS[key]=replace(jobs.DEFINITIONS[key],compute=fault)
 return trace
sys.argv=['job_runner','--once'];sys.settrace(trace)
runpy.run_module('modular_platform.job_runner',run_name='__main__')
""".replace('mode=MODE','mode='+repr(mode))
    args+=['-c',wrapper]
    ident=f.command(label+'-create',args).decode().strip();return name,ident
def start(label,name):
    out=j.LOCAL/'logs'/(label+'.stdout');err=j.LOCAL/'logs'/(label+'.stderr');assert not out.exists()
    stdout=out.open('xb');stderr=err.open('xb');process=subprocess.Popen(['docker','start','-a',name],stdout=stdout,stderr=stderr,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    return process,stdout,stderr,out,err
def barrier(handle):
    process,_,_,out,_=handle;deadline=time.monotonic()+45
    while time.monotonic()<deadline:
        rows=[json.loads(line.split('MP_BARRIER=',1)[1]) for line in out.read_text().splitlines() if line.startswith('MP_BARRIER=')]
        if rows:assert len(rows)==1;return rows[0]
        assert process.poll() is None,'Inspect the exact terminal runner; never restart'
        time.sleep(0.1)
    raise AssertionError('Inspect exact live runner/handle; barrier unobserved')
def finish(handle,expected=0):
    process,out,err,path,error=handle;process.wait(timeout=45);out.close();err.close();assert process.returncode==expected
    return [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')]

baseline=json.loads(f.sql(state,'core11-runner-before',"SELECT jsonb_build_object('jobs',(SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j),'notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'events',(SELECT jsonb_agg(to_jsonb(e) ORDER BY id) FROM mp_outbox e),'membership',(SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m),'control',(SELECT to_jsonb(c) FROM mp_dispatch_control c));"))
assert len(baseline['jobs'])==6 and all(row['state'] in {'completed','dead_letter'} for row in baseline['jobs'])
f.write(j.LOCAL/'core11-runner-before.json',baseline)

kill=seed('core11-kill-seed',True);name,ident=create('core11-killed-runner','kill');handle=start('core11-killed-runner',name)
invocation=barrier(handle);assert invocation['claim']['job_id']==kill['job_id'] and invocation['database']==state['active_db'];f.write(j.LOCAL/'core11-killed-invocation.json',invocation)
before=snapshot('core11-before-kill',kill);assert before['state']=='running' and before['revision']==1
f.command('core11-actual-kill',['docker','kill','--signal','KILL',name]);finish(handle,137)
row=json.loads(subprocess.check_output(['docker','inspect',ident]))[0];assert row['State']['ExitCode']==137
after=snapshot('core11-after-kill',kill);assert after['revision']==1 and after['attempts']==1 and 0<=after['lease_remaining']<=30
f.write(MARKER,dict(state='killed_waiting_actual_lease',container_id=ident,job_id=kill['job_id']));print('Real SIGKILL137 after committed claim; waiting '+str(round(after['lease_remaining'],1))+' seconds for actual lease',flush=True)
time.sleep(after['lease_remaining']+0.2)
cli('core11-reclaim-normal-cli');result=snapshot('core11-after-reclaim',kill)
assert result['state']=='completed' and result['attempts']==result['generation']==2 and result['revision']==2 and result['write_uid']==kill['user_id'] and result['title']==' '.join(kill['title'].split())
code="from modular_platform import durable\nvalue="+repr(invocation)+"\nvalue['claim']=durable.Claim(**value['claim']);invocation=jobs.Invocation(**value)\ntry:jobs.finish_one(env,invocation,jobs.compute(invocation))\nexcept durable.ClaimLost:env.cr.rollback();print('MP_RUNNER='+json.dumps(dict(stale_claim_denied=True)))\nelse:raise AssertionError('Stale claim applied')"
assert native('core11-stale-claim',code)['stale_claim_denied']
f.save('lease.json',dict(result='passed_current_installed_death_reclaim',image_id=state['image_id'],actual_SIGKILL_exit=137,attempts=2,revision=2,one_original_user_effect=True,obsolete_claim_denied=True,runner_source_substitution=False,trace_instrumentation='Pause before compute only; normal CLI reclaimed the actual expired lease'))

revoked=seed('core11-revoke-seed',True);name,ident=create('core11-revoked-runner','revoke');handle=start('core11-revoked-runner',name);assert barrier(handle)['claim']['job_id']==revoked['job_id']
actor=next(r['principal_id'] for r in baseline['membership'] if r['workspace_id']==fixture['workspaces']['C']['id'] and r['role']=='administrator')
member=next(r for r in baseline['membership'] if r['principal_id']==actor and r['workspace_id']==fixture['workspaces']['C']['id'])
query="UPDATE mp_membership SET role='viewer' WHERE id="+str(member['id'])+' RETURNING role;'
assert f.sql(state,'core11-demote-during-compute',query).strip()==b'viewer'
try:
    f.command('core11-release-revoked-runner',['docker','exec',ident,'/venv/bin/python','-c',"from pathlib import Path;Path('/tmp/fixture-resume').write_text('resume')"])
    rows=finish(handle);assert rows==[dict(job_id=revoked['job_id'],state='dead_letter',error_code='FORBIDDEN')]
finally:f.sql(state,'core11-restore-original-role',"UPDATE mp_membership SET role='"+member['role']+"' WHERE id="+str(member['id'])+';')
result=snapshot('core11-revocation-final',revoked);assert result['state']=='dead_letter' and result['error_code']=='FORBIDDEN' and result['revision']==1 and result['title']==revoked['title']
f.save('revocation.json',dict(result='passed_installed_compute_to_apply_revocation',image_id=state['image_id'],actor_role_committed_between_compute_and_apply=True,no_business_effect=True,original_role_restored=True,runner_source_substitution=False,trace_instrumentation='Pause immediately before actual finalization only'))

errors={}
for mode in ['unavailable','cancel']:
    job=seed('core11-'+mode+'-seed',False);name,ident=create('core11-'+mode+'-runner',mode);handle=start('core11-'+mode+'-runner',name)
    expected=0 if mode=='unavailable' else 1
    rows=finish(handle,expected);result=snapshot('core11-'+mode+'-final',job)
    if mode=='unavailable':assert rows==[dict(job_id=job['job_id'],state='dead_letter',error_code='DEPENDENCY_UNAVAILABLE')] and result['error_code']=='DEPENDENCY_UNAVAILABLE'
    else:
        assert rows==[dict(state='error',error_code='INTERNAL_ERROR')] and result['state']=='running' and result['cancel_requested']
        assert 'Safe registered failure code required' in handle[4].read_text()
        f.write(MARKER,dict(state='cancel_error_reproduced_waiting_lease',container_id=ident,job_id=job['job_id']))
        assert 0<=result['lease_remaining']<=30
        print('Reproduced installed cancellation error-code mismatch; preserving diagnostics and waiting for cancelled owned claim expiry',flush=True)
        time.sleep(result['lease_remaining']+0.2);cli('core11-cancel-reaper-normal-cli')
        final=snapshot('core11-cancel-reaped',job);assert final['state']=='cancelled' and final['attempts']==1
    errors[mode]=dict(job_id=job['job_id'],observed_state=result['state'],exit_code=expected,compute_fault_instrumentation=True)
f.save('errors.json',dict(result='unavailable_passed_cancel_defect_reproduced',image_id=state['image_id'],cases=errors,cancellation_uses_actual_bridge_snapshot_and_real_cancel_flag=True,defect='Runner maps CANCELLED then durable.fail rejects that nonfailure code, emitting INTERNAL_ERROR instead of claim_lost',cancelled_owned_job_reaped_without_replay=True))
after=json.loads(f.sql(state,'core11-runner-after',"SELECT jsonb_build_object('jobs',(SELECT jsonb_agg(to_jsonb(j) ORDER BY id) FROM mp_job j),'notes',(SELECT jsonb_agg(to_jsonb(n) ORDER BY id) FROM mp_example_note n),'events',(SELECT jsonb_agg(to_jsonb(e) ORDER BY id) FROM mp_outbox e),'membership',(SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM mp_membership m),'control',(SELECT to_jsonb(c) FROM mp_dispatch_control c));"))
for key in ['jobs','notes','events']:
    current={row['id']:row for row in after[key]}
    assert all(current[row['id']]==row for row in baseline[key]),key
assert after['membership']==baseline['membership'] and after['control']==baseline['control']
assert not any(row['state'] in {'pending','running','retry'} for row in after['jobs'])
f.write(j.LOCAL/'core11-runner-after.json',after);f.write(MARKER,dict(state='completed_with_cancel_defect',jobs=len(after['jobs']),notes=len(after['notes']),events=len(after['events'])));f.phase(state,'core11_runner_cancel_defect_reproduced');f.guard(state)
print('Installed lease/reclaim/revocation/unavailable checks pass; cancellation defect reproduced with all owned jobs terminal and original data/authority exact')
