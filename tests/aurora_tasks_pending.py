"""Real old47 workspace jobs/claim carried across the new native-app transition."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'packages/platform_sdk')]
from aurora_tasks_release_site import ReleaseSite,load,write
from modular_platform import tasks_adoption as ta


SEED='''
import dataclasses,json
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import job_dispatch
from modular_platform.durable import JobSchedule
from modular_platform.job_runner import _claim_guard
registry=env.registry
jobs={}
with registry.cursor() as cr:
 for label,who,space in [('claimed','alice','A'),('pending','alice','A'),('other_actor','bob','B')]:
  actor=scoped_environment(api.Environment(cr,FIXTURE['users'][who]['id'],{},su=False),FIXTURE['workspaces'][space]['public_id'])
  now=datetime.now(timezone.utc)
  jobs[label]=job_dispatch.enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:report',
   dict(first=1,last=500),'at04-source-'+label,version=2,schedule=JobSchedule(now,now+timedelta(hours=12),20))
 cr.commit()
with registry.cursor() as cr:
 with _claim_guard(cr,'bulk',FIXTURE['workspaces']['A']['id']) as allowed:
  assert allowed
  invocation=job_dispatch.prepare_one(api.Environment(cr,1,{}),str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['A']['id'],lease_seconds=30)
  assert invocation.claim.job_id==jobs['claimed']
  cr.commit()
print('MP_AT_PENDING='+json.dumps(dict(jobs=jobs,invocation=dataclasses.asdict(invocation)),default=lambda v:v.isoformat()))
'''

STALE='''
import json
from datetime import datetime
from odoo import api
from odoo.addons.mp_core import job_dispatch
from modular_platform.durable import Claim,ClaimLost,DispatchPaused
claim=dict(SAVED['invocation']['claim'])
if claim.get('budget_until'):claim['budget_until']=datetime.fromisoformat(claim['budget_until'])
data=dict(SAVED['invocation']);data['claim']=Claim(**claim)
old=job_dispatch.Invocation(**data)
with env.registry.cursor() as cr:
 try:
  job_dispatch.finish_one(api.Environment(cr,1,{}),old,dict(count=2,points=13,digest='0'*64))
 except (ClaimLost,DispatchPaused):pass
 else:raise AssertionError('Obsolete original claim accepted after publication/recovery')
 cr.rollback()
print('MP_AT_STALE='+json.dumps(dict(result='denied',job=old.claim.job_id)))
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['seed','stale'])
    p.add_argument('--run',required=True);p.add_argument('--site',choices=['tasks','maintenance'],required=True)
    p.add_argument('--port',type=int,required=True);p.add_argument('--label',default='after-forward')
    args=p.parse_args();site=ReleaseSite(args);state=site.state();target=load(site.private/'target.json')
    state.update(image_id=target['image_id'],database=target['sites'][0]['database'])
    if args.action=='seed':
        path=site.local/'source-pending.json';assert not path.exists()
        assert target['image_id']==ta.SOURCE_IMAGE
        raw=site.native(dict(state),'source-pending-seed',[],'FIXTURE='+repr(load(site.local/'fixtures.json'))+'\n'+SEED)
        rows=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_PENDING=')]
        assert len(rows)==1;write(path,rows[0])
    else:
        assert args.label.replace('-','').isalnum()
        path=site.local/('stale-'+args.label+'.json');assert not path.exists()
        raw=site.native(dict(state),'stale-'+args.label,[],'SAVED='+repr(load(site.local/'source-pending.json'))+'\n'+STALE)
        rows=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_STALE=')]
        assert len(rows)==1;write(path,rows[0])
    write(site.local/'state.json',state)
    print(json.dumps(dict(result='recorded',action=args.action,site=args.site)))


if __name__=='__main__':main()
