"""Actual native reminder carry-forward through an approved later release publication."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_release_site import ReleaseSite,load,write
from foundation_release import FoundationSite

SEED='''
import dataclasses,json
from datetime import timedelta
from uuid import uuid4
from odoo import api,fields
from odoo.addons.mp_core import job_dispatch
from modular_platform.job_runner import _claim_guard
registry=env.registry
with registry.cursor() as cr:
 actor=api.Environment(cr,FIXTURE['users']['alice']['id'],{},su=False)
 listing=actor['mp.aurora.task.list'].create(dict(name='Native publication witness'))
 tasks=actor['mp.aurora.task'].create([dict(name='Publication reminder '+str(i),list_id=listing.id,
  assignee_id=FIXTURE['users']['operator']['id'],due_date=fields.Datetime.now()-timedelta(seconds=1),reminder='0') for i in range(2)])
 cr.execute('SELECT job_id FROM mp_aurora_reminder WHERE task_id=ANY(%s) ORDER BY task_id',[tasks.ids]);jobs=[r[0] for r in cr.fetchall()]
 assert len(jobs)==2
 cr.execute('SELECT installation_id FROM mp_job WHERE public_id=%s',[jobs[0]]);installation=cr.fetchone()[0]
 ids=tasks.ids
 cr.commit()
with registry.cursor() as cr:
 with _claim_guard(cr,'urgent',None,installation) as allowed:
  assert allowed
  old=job_dispatch.prepare_one(api.Environment(cr,1,{}),str(uuid4()),pool='urgent',native_installation_id=installation,lease_seconds=30)
  assert old.claim.job_id==jobs[0]
  cr.commit()
print('MP_AT_PUBLICATION='+json.dumps(dict(tasks=ids,jobs=jobs,invocation=dataclasses.asdict(old)),default=lambda v:v.isoformat()))
'''

VERIFY='''
import json
from datetime import datetime
from odoo import api
from odoo.addons.mp_core import job_dispatch
from modular_platform.durable import Claim,ClaimLost,DispatchPaused
data=dict(SAVED['invocation']);claim=dict(data['claim'])
if claim.get('budget_until'):claim['budget_until']=datetime.fromisoformat(claim['budget_until'])
data['claim']=Claim(**claim)
with env.registry.cursor() as cr:
 try:job_dispatch.finish_one(api.Environment(cr,1,{}),job_dispatch.Invocation(**data),{})
 except (ClaimLost,DispatchPaused):pass
 else:raise AssertionError('Original pre-publication native claim accepted')
 cr.rollback()
print('MP_AT_PUBLICATION='+json.dumps(dict(stale_original_native_claim_denied=True)))
'''


def snapshot(site,state,jobs):
    ids=','.join("'"+j+"'" for j in jobs)
    # Fixed identity/resource/actor/payload/timing projection. Generation changes
    # are inspected separately; they may not rewrite business or deduplication data.
    query="SELECT jsonb_object_agg(public_id,jsonb_build_object('site',site_id,'workspace',workspace_id,'actor',actor_id,'installation',installation_id,'handler',handler,'version',handler_version,'key',idempotency_key,'payload',payload,'digest',input_digest,'at',available_at,'deadline',deadline_at,'max_attempts',max_attempts)) FROM mp_job WHERE public_id IN ("+ids+");"
    import time
    return json.loads(site.sql(state,'native-publication-snapshot-'+str(time.monotonic_ns()),query))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['seed','publish','verify','effects'])
    p.add_argument('--run',required=True);p.add_argument('--port',type=int,default=18149)
    a=p.parse_args();a.site='tasks';site=ReleaseSite(a);state=site.state();target=load(site.private/'target.json')
    state.update(image_id=target['image_id'],database=target['sites'][0]['database'])
    path=site.local/'native-publication.json'
    if a.action=='seed':
        assert not path.exists()
        assert load(site.local/'tasks-forward.json')['phase']=='verified'
        raw=site.native(state,'native-publication-seed',[],'FIXTURE='+repr(load(site.local/'fixtures.json'))+'\n'+SEED)
        result,=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_PUBLICATION=')]
        result.update(phase='seeded',before=snapshot(site,state,result['jobs']),old_generation=target['generation'])
    else:
        result=load(path)
        if a.action=='publish':
            assert result['phase']=='seeded'
            FoundationSite.install_selected(site,['org.example.notes_labels'],'native-publication-labels')
            result.update(phase='published',operation=load(site.local/'native-publication-labels.json')['operation_id'])
        elif a.action=='verify':
            assert result['phase']=='published' and target['generation']>result['old_generation']
            after=snapshot(site,state,result['jobs'])
            from datetime import datetime
            # Reconciliation rebases the ready-queue eligibility timestamp for
            # overdue work. The immutable schedule in payload, deadline, actor,
            # input and deduplication identity must remain exactly unchanged.
            for ident,before in result['before'].items():
                current=dict(after[ident]);original=dict(before)
                assert datetime.fromisoformat(current.pop('at'))>=datetime.fromisoformat(original.pop('at'))
                assert current==original
            ids=','.join("'"+j+"'" for j in result['jobs'])
            assert site.sql(state,'native-publication-ready-now',"SELECT bool_and(available_at<=timezone('UTC',clock_timestamp())) FROM mp_job WHERE public_id IN ("+ids+");").strip()==b't'
            assert all(r['workspace'] is None for r in result['before'].values())
            raw=site.native(state,'native-publication-stale',[],'SAVED='+repr(result)+'\n'+VERIFY)
            check,=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_PUBLICATION=')]
            result.update(phase='verified_carry_forward',**check,new_generation=target['generation'],identity_actor_payload_timing_preserved=True,overdue_ready_queue_rebased_without_future_delay=True)
        else:
            assert result['phase']=='verified_carry_forward'
            ids=','.join("'"+j+"'" for j in result['jobs'])
            rows=json.loads(site.sql(state,'native-publication-effects',"SELECT jsonb_agg(jsonb_build_object('id',public_id,'state',state,'attempts',attempts,'result',result)) FROM mp_job WHERE public_id IN ("+ids+");"))
            assert len(rows)==2 and all(r['state']=='completed' and r['result']==dict(outcome='notified') for r in rows),rows
            for r in rows:assert r['attempts']==(2 if r['id']==result['jobs'][0] else 1),rows
            taskids=','.join(map(str,result['tasks']))
            assert site.sql(state,'native-publication-notifications','SELECT count(*),count(DISTINCT task_id) FROM mp_aurora_notification WHERE task_id IN ('+taskids+');').strip()==b'2|2'
            result.update(phase='verified',effects=2,rows=rows)
    write(path,result);write(site.local/'state.json',state)
    print(json.dumps(dict(action=a.action,result=result['phase'])))


if __name__=='__main__':main()
