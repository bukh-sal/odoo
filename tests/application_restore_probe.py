"""Rollback-only actual sealed-image regression of ADR0079's host adapter."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from application_adoption_site import AdoptionSite,load,write

BODY='''
import json
from odoo import api
from odoo.addons.mp_core import job_dispatch
from odoo.addons.mp_identity.release import current_release
from modular_platform.plans import data_digest
ns={'__name__':'reviewed_host_restore_adapter'}
exec(compile(ADAPTER_SOURCE,'reviewed_host_restore_adapter','exec'),ns)
reconcile=ns['reconcile_transaction']
def original(cr):
 cr.execute('SELECT to_jsonb(j) FROM mp_job j ORDER BY id');jobs=cr.fetchall()
 cr.execute('SELECT site_id,release_digest,state,generation FROM mp_dispatch_control');control=cr.fetchall()
 return data_digest(dict(jobs=jobs,control=control))
with env.registry.cursor() as cr:before=original(cr);cr.rollback()
checks=[]
for case in ['valid','revoked_actor','wrong_source','enabled_control','exception_rollback']:
 try:
  with env.registry.cursor() as cr:
   meta=api.Environment(cr,1,{})
   release=current_release(meta)
   cr.execute('SELECT to_jsonb(j) FROM mp_job j ORDER BY id');rows=[x[0] for x in cr.fetchall()]
   source=rows[0]['release_digest'];assert all(r['release_digest']==source for r in rows)
   data=dict(site_id=release['site_id'],previous_release=release['release_digest'],release_digest=release['release_digest'],source_release=source)
   if case!='enabled_control':cr.execute("UPDATE mp_dispatch_control SET state='paused'")
   if case=='revoked_actor':cr.execute("UPDATE mp_principal SET state='suspended' WHERE id=%s",[rows[0]['actor_id']])
   if case=='wrong_source':data['source_release']='sha256:'+'f'*64
   def invoke(previous,target):
    if case=='exception_rollback':raise RuntimeError('deliberate classification failure')
    return job_dispatch.reconcile_release(meta,previous_release=previous,target_release=target)
   try:result=reconcile(cr,data,invoke)
   except ValueError as error:
    assert case=='enabled_control' and str(error)=='Exact closed restored control required';checks.append(case)
   else:
    assert case in {'valid','revoked_actor','wrong_source'}
    if case=='valid':
     assert all(d['decision']=='resumable' and d['state']=='pending' for d in result['jobs']),result
     cr.execute('SELECT to_jsonb(j) FROM mp_job j ORDER BY id');after=[x[0] for x in cr.fetchall()]
     for old,new in zip(rows,after):
      for field in ['public_id','workspace_id','actor_id','installation_id','payload','idempotency_key','input_digest','deadline_at','attempts']:
       assert old[field]==new[field],field
      assert new['claim_generation']>old['claim_generation']
    else:assert all(d['state']=='held' and d['error_code']=='FORBIDDEN' for d in result['jobs']),result
    cr.execute('SELECT release_digest,state FROM mp_dispatch_control');assert cr.fetchone()==(release['release_digest'],'paused')
    checks.append(case)
   cr.rollback()
 except RuntimeError as error:
  assert case=='exception_rollback' and str(error)=='deliberate classification failure';checks.append(case)
 with env.registry.cursor() as cr:assert original(cr)==before;cr.rollback()
print('AP_RESTORE_PROBE='+json.dumps(dict(result='passed',cases=checks,actual_postgresql_rollback=True,
 sealed_runtime_unchanged=True,business_effects_applied=0,original_job_actor_payload_schedule_preserved=True)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',default='ap02-release-01');p.add_argument('--port',type=int,default=18173);a=p.parse_args()
    site=AdoptionSite(a);path=site.local/'host-restore-probe.json';assert not path.exists()
    assert load(site.local/'fault-operation.json')['phase']=='failed_restored_job_authorization'
    assert load(site.local/'counterexample-fleet-drained.json')['state']=='paused'
    state=site.state();target=load(site.private/'target.json');state.update(image_id=target['image_id'],database=target['sites'][0]['database'])
    code='ADAPTER_SOURCE='+repr((ROOT/'packages/platform_sdk/modular_platform/dispatch_jobs_maintenance.py').read_text(encoding='utf-8'))+'\n'+BODY
    raw=site.native(state,'host-restore-probe',[],code)
    result=next(json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('AP_RESTORE_PROBE='))
    write(path,result);write(ROOT/'docs/evidence/post-r1/application-adoption/ap02-host-restore-probe.json',result);print(json.dumps(result))

if __name__=='__main__':main()
