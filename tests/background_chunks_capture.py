"""Capture committed BX-05 progress after the refused final snapshot clear."""
from background_workers import Probe
from background_sustained import native
from background_site import write

probe=Probe('bx-05-chunks-01',extra_phase='bx05-basic-resume')
probe.state['phase']='background_installed'
result=native(probe,'bx05-finalization-capture',"""
import json,hashlib
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
model=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])['mp.background.task']
env.cr.execute("SELECT public_id FROM mp_background_report WHERE request_key='bx05-snapshot'")
ident,=env.cr.fetchone();row=model._report_row(ident)
assert row['cursor']==1200 and row['points']==519400 and row['total']==1201
assert row['state']=='running' and len(row['snapshot'])==1201
env.cr.execute("SELECT state,count(*),sum((result->>'count')::int) FROM mp_job WHERE handler='org.example.background:report_chunk' GROUP BY state")
states={state:dict(jobs=count,rows=counted) for state,count,counted in env.cr.fetchall()}
assert states.get('completed')==dict(jobs=12,rows=1200)
assert sum(value['jobs'] for value in states.values())==13
env.cr.rollback()
print('BX04_RESULT='+json.dumps(dict(run=ident,row=row,states=states,final_chunk_rolled_back=True)))
""")
write(probe.site.local/'bx05-finalization-gap.json',result)
print(dict(cursor=result['row']['cursor'],points=result['row']['points'],states=result['states']))
