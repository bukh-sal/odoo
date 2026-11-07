"""Read-only diagnosis of the preserved first BX-05 job refusal."""
from background_workers import Probe
from background_sustained import native

probe=Probe('bx-05-chunks-01',extra_phase='bx05-basic')
probe.state['phase']='background_installed'
print(native(probe,'bx05-diagnose-01',"""
import json,traceback
from odoo import api
from odoo.addons.mp_core import job_dispatch as jobs
env.cr.execute("SELECT to_jsonb(j) FROM mp_job j WHERE handler='org.example.background:report_chunk'")
job,=env.cr.fetchone();definition=jobs.DEFINITIONS[(job['handler'],job['handler_version'])]
actor,payload=jobs._environment(env,job)
scope,release,bound=jobs._authorize(actor,definition,payload['context']['alias'])
result=dict(state=job['state'],error=job['error_code'],binding_equal=bound.binding==payload['context']['binding'],
    release_equal=release['release_digest']==job['release_digest'])
try:
    jobs._authorized_job(env,job)
    result['authorized']=True
except Exception as error:
    result['authorized_error']=type(error).__name__;result['trace']=traceback.format_exc()
row=bound.model._report_row(payload['input']['run'])
result['run']=dict(state=row['state'],cursor=row['cursor'],contract=row['contract_version'],total=row['total'])
try:
    prepared=definition.prepare(actor,payload['input'],bound)
    computed=definition.compute(prepared,{})
    _,current=bound.model._report_stage(payload['input'])
    result.update(prepared_equal=current==prepared,computed_count=computed['count'],computed_points=computed['points'])
except Exception as error:
    result['stage_error']=type(error).__name__;result['stage_trace']=traceback.format_exc()
env.cr.rollback()
print('BX04_RESULT='+json.dumps(result))
"""))
