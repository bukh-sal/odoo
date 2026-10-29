"""Actual guarded native runner and SIGKILL/reclaim on this owned test site."""
import argparse,dataclasses,json,subprocess,time
import g6_job_fixture as fixture
f=fixture.f;ROOT=fixture.ROOT;LOCAL=fixture.LOCAL;OUTPUT=fixture.OUTPUT.parent


def native(state,label,source):
    raw=f.native(state,label,[],source)
    rows=[json.loads(line.split('MP_PROCESS=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_PROCESS=')]
    assert len(rows)==1,'Inspect exact stopped child/private diagnostics before continuation'
    return rows[0]


def runner(state,label,*,pin=None,barrier=False):
    name=state['project']+'-'+label
    argv=['docker','create','--name',name,'--log-driver','none','--label','com.modular.disposable='+state['project'],'--network',state['project']+'_runtime','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp','--memory','768m','--pids-limit','128','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular','--env','MP_EXPECTED_DATABASE='+state['active_db'],'--env','MP_EXPECTED_INVENTORY_DIGEST='+(pin or state['inventory_digest']),'--entrypoint','/venv/bin/python',state['image_id']]
    if barrier:
        # Fixture instrumentation observes the actual runner after its short
        # claim/preflight transaction committed. No product delay/fault flag.
        wrapper="""import dataclasses,json,pathlib,runpy,sys,time
path='/opt/modular/packages/platform_sdk/modular_platform/job_runner.py'
line=next(i for i,text in enumerate(pathlib.Path(path).read_text().splitlines(),1) if text.strip()=='computed=jobs.compute(invocation)')
def trace(frame,event,arg):
 if event=='line' and frame.f_code.co_filename==path and frame.f_lineno==line:
  print('MP_JOB_BARRIER='+json.dumps(dataclasses.asdict(frame.f_locals['invocation'])),flush=True)
  time.sleep(300)
 return trace
sys.argv=['job_runner','--once'];sys.settrace(trace)
runpy.run_module('modular_platform.job_runner',run_name='__main__')
"""
        argv+=['-c',wrapper]
    else:argv+=['-m','modular_platform.job_runner','--once']
    ident=f.command(label+'-create',argv).decode().strip()
    return name,ident


def start(state,label,name,*,expect_failure=False):
    stdout=LOCAL/'logs'/(label+'.stdout');stderr=LOCAL/'logs'/(label+'.stderr')
    with stdout.open('xb') as out,stderr.open('xb') as err:
        result=subprocess.run(['docker','start','-a',name],stdout=out,stderr=err,timeout=120)
    assert (result.returncode!=0)==expect_failure,'Inspect retained child and diagnostics; never rerun a job blindly'
    child=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    assert not child['State']['Running']
    return stdout.read_text(encoding='utf8'),stderr.read_text(encoding='utf8'),child


def make_job(state,label):
    code="""import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.job_dispatch import enqueue_bound
from modular_platform import durable
fixture=FIXTURE
env.cr.rollback();cr=env.cr
cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=cr.fetchone()[0]
durable.set_control(cr,fixture['site_id'],release,'enabled')
alice=fixture['users']['alice'];workspace=fixture['workspaces']['A']
cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes' AND state='installed'");consumer=cr.fetchone()[0]
native=scoped_environment(api.Environment(cr,alice['id'],{}),workspace['public_id'])
native=native(context={**native.context,'_mp_call_frame':CallFrame(alice['principal_id'],workspace['public_id'],fixture['site_id'],consumer,'org.example.notes',())})
note=native['mp.example.note'].create(dict(title='Native   runner  '+uuid4().hex));native.flush_all()
ident=enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=note.public_id,expected_revision=1),uuid4().hex)
result=dict(job_id=ident,note_id=note.public_id,title=note.title,user_id=alice['id'])
cr.commit();print('MP_PROCESS='+json.dumps(result))
""".replace('fixture=FIXTURE','fixture=json.loads('+repr((LOCAL/'fixtures.json').read_text())+')')
    result=native(state,label,code);f.write(LOCAL/(label+'.json'),result);return result


def snapshot(state,label,job):
    return json.loads(f.sql(state,label,"SELECT jsonb_build_object('state',j.state,'attempts',j.attempts,'generation',j.claim_generation,'job_result',j.result,'title',n.title,'revision',n.revision,'write_uid',n.write_uid,'lease_remaining',GREATEST(0,extract(epoch FROM j.lease_until-timezone('UTC',clock_timestamp())))) FROM mp_job j JOIN mp_example_note n ON n.public_id=j.payload->'input'->>'note_id' WHERE j.public_id='"+job['job_id']+"';"))


def assert_completed(record,job,attempts):
    assert record['state']=='completed' and record['attempts']==attempts and record['generation']==attempts
    assert (record['title'],record['revision'],record['write_uid'])==(' '.join(job['title'].split()),2,job['user_id'])
    assert record['job_result']==dict(note_id=job['note_id'],revision=2,changed=True)


def main():
    global LOCAL,OUTPUT
    parser=argparse.ArgumentParser();parser.add_argument('--profile',choices=['authorization','runner'],default='authorization');args=parser.parse_args()
    fixture.select_profile(args.profile);LOCAL=fixture.LOCAL;OUTPUT=fixture.OUTPUT.parent
    state=f.load(LOCAL/'state.json');f.guard(state);assert state['phase']==('references_installed' if args.profile=='runner' else 'job_tests_verified')
    marker=LOCAL/'process.json';assert not marker.exists();f.write(marker,dict(phase='starting'))
    name,ident=runner(state,'job-runner-bad-pin',pin='sha256:'+'0'*64)
    out,err,child=start(state,'job-runner-bad-pin',name,expect_failure=True)
    assert 'Independent job database and inventory pins required' in err and 'odoo.modules.loading' not in err
    assert not out.strip()
    first=make_job(state,'process-enqueue-normal')
    name,_=runner(state,'job-runner-normal');out,err,child=start(state,'job-runner-normal',name)
    rows=[json.loads(line) for line in out.splitlines() if line.startswith('{')];assert rows==[dict(job_id=first['job_id'],state='completed')]
    normal=snapshot(state,'process-normal-after',first);assert_completed(normal,first,1)
    second=make_job(state,'process-enqueue-kill')
    name,ident=runner(state,'job-runner-killed',barrier=True)
    label='job-runner-killed';out_path=LOCAL/'logs'/(label+'.stdout');err_path=LOCAL/'logs'/(label+'.stderr')
    f.write(marker,dict(phase='waiting_for_claim_barrier',container=name,container_id=ident,job_id=second['job_id']))
    with out_path.open('xb') as out,err_path.open('xb') as err:
        process=subprocess.Popen(['docker','start','-a',name],stdout=out,stderr=err)
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            lines=[line.split('MP_JOB_BARRIER=',1)[1] for line in out_path.read_text(encoding='utf8').splitlines() if line.startswith('MP_JOB_BARRIER=')]
            if lines:break
            if process.poll() is not None:raise AssertionError('Runner exited before barrier; inspect retained diagnostics')
            time.sleep(0.2)
        else:raise AssertionError('Inspect owned live runner before continuation; barrier outcome uncertain')
        assert len(lines)==1;invocation=json.loads(lines[0]);assert invocation['claim']['job_id']==second['job_id']
        f.write(LOCAL/'killed-invocation.json',invocation)
        before=snapshot(state,'process-before-kill',second)
        assert before['state']=='running' and before['attempts']==before['generation']==1 and before['revision']==1 and before['title']==second['title']
        f.command('process-kill-signal',['docker','kill','--signal','KILL',name]);process.wait(timeout=15)
    child=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    assert not child['State']['Running'] and child['State']['ExitCode']==137
    f.write(marker,dict(phase='killed_waiting_for_lease',container=name,job_id=second['job_id'],claim_generation=1))
    after_kill=snapshot(state,'process-after-kill',second);assert after_kill['revision']==1 and after_kill['attempts']==1
    print(json.dumps(dict(state='killed_after_committed_claim',job_id=second['job_id'],waiting_for_bounded_lease_seconds=round(after_kill['lease_remaining'],2))),flush=True)
    assert 0<=after_kill['lease_remaining']<=30;time.sleep(after_kill['lease_remaining']+0.2)
    name,_=runner(state,'job-runner-reclaim');out,err,child=start(state,'job-runner-reclaim',name)
    rows=[json.loads(line) for line in out.splitlines() if line.startswith('{')];assert rows==[dict(job_id=second['job_id'],state='completed')]
    recovered=snapshot(state,'process-reclaim-after',second);assert_completed(recovered,second,2)
    code="""import json
from odoo.addons.mp_core import job_dispatch as jobs
from modular_platform import durable
value=INVOCATION
value['claim']=durable.Claim(**value['claim']);invocation=jobs.Invocation(**value)
try:jobs.finish_one(env,invocation,jobs.compute(invocation))
except durable.ClaimLost:env.cr.rollback();print('MP_PROCESS='+json.dumps(dict(stale_claim_denied=True)))
else:raise AssertionError('Obsolete real worker claim applied')
""".replace('value=INVOCATION','value=json.loads('+repr(json.dumps(invocation))+')')
    assert native(state,'process-stale-finalize',code)==dict(stale_claim_denied=True)
    code="""import json
from modular_platform import durable
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");site=env.cr.fetchone()[0]
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=env.cr.fetchone()[0]
durable.set_control(env.cr,site,release,'paused');env.cr.commit();print('MP_PROCESS='+json.dumps(dict(paused=True)))
"""
    assert native(state,'process-pause',code)==dict(paused=True)
    f.guard(state);f.phase(state,'job_processes_verified');f.write(marker,dict(phase='completed',native_processes=4,actual_SIGKILL=True))
    path=OUTPUT/'process-checks.json';assert not path.exists()
    f.write(path,dict(result='passed',image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'],bad_pin_denied_before_native_import=True,normal_job=first['job_id'],normal_attempts=1,killed_job=second['job_id'],actual_exit_code=137,business_revision_at_death=1,reclaimed_attempts=2,reclaimed_business_revision=2,original_user_write_uid=True,stale_original_claim_denied=True,all_children_terminal=True,dispatch='paused',limits=['Native runner proof only. Scoped events/external worker/lifecycle/queue-aware recovery remain pending. All job and business rows retained.']))
    print(json.dumps(dict(result='passed',actual_SIGKILL=True,reclaimed_once=True,dispatch='paused')))


if __name__=='__main__':main()
