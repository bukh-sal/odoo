"""Native schema recognition and refusal before the recurrence profile is enabled."""
import json
from uuid import uuid4

from background_workers import Probe
from background_site import configuration,write
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import OperationLocks,OperatorError
from modular_platform.plans import data_digest


SOURCE="""
import json
from datetime import datetime,timezone
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment,current_scope
from odoo.addons.mp_identity.release import current_release
from modular_platform import durable,recurrence_store
from modular_platform.recurrence import RecurrenceRule
from modular_platform.dispatch_lifecycle import PHYSICAL_SCHEMA,_schema
assert env.cr.dbname==EXPECTED_DB
assert set(_schema(env.cr))==set(PHYSICAL_SCHEMA)
actor=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])
scope=current_scope(actor);release=current_release(env)
env.cr.execute("SELECT id FROM mp_plugin_installation WHERE plugin_id='org.example.background'")
installation,=env.cr.fetchone()
# Deliberately synthetic privileged metadata, not the native service adapter.
# Its presence must make the generic lifecycle refuse maintenance.
storage=durable.DispatchScope(release['site_id'],scope.workspace_id,scope.principal_id,installation,release['release_digest'])
rule=RecurrenceRule(datetime.now(timezone.utc).replace(microsecond=0),60,3600,5)
ident=recurrence_store.create(env.cr,storage,'org.example.background:fault',1,
    dict(input={'mode':'heartbeat'},context={'credential_id':None}),rule,'schema-guard',authorize=lambda _:None)
for name in ('mp.job.schedule','mp.job.occurrence'):
    try:actor[name].search([],limit=1)
    except AccessError:pass
    else:raise AssertionError('Private recurrence metadata has public ORM read authority')
env.cr.commit()
print('BX03_SCHEMA='+json.dumps(dict(schedule=ident,tables=sorted(PHYSICAL_SCHEMA),private_model_access_denied=True)))
"""


def run():
    probe=Probe('bx-03-recurrence-01')
    path=probe.site.local/'bx03-schema.json'
    assert not path.exists()
    source='EXPECTED_DB='+repr(probe.state['database'])+'\nFIXTURE='+repr(probe.fixture)+'\n'+SOURCE
    raw=probe.site.native(dict(probe.state),'bx03-schema',[],source).decode()
    write(probe.site.local/'state.json',probe.state)
    result,=[json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BX03_SCHEMA=')]
    target=probe.site.private/'target.json'
    executor=NativeExecutor(probe.operator.store,target,probe.site.private/'catalog',configuration(probe.site.private/'trust.json'))
    helper=executor._dispatch()
    observed=helper.inspect()
    assert observed['recurring_schedules']==1 and observed['active_credentials']==0
    try:helper.require_profile(observed)
    except OperatorError:result['host_generic_profile_refused_populated_recurrence']=True
    else:raise AssertionError('Generic profile admitted recurrence metadata')
    before=probe.sql("SELECT jsonb_build_object('state',state,'generation',generation,'release',release_digest) FROM mp_dispatch_control")
    operation=str(uuid4())
    with OperationLocks(probe.operator.store.root/'locks',probe.operator.deployment,[probe.operator.site['site_id']]):
        probe.operator._authorize()
        try:helper.run('fence',operation,probe.site.local/'recurrence-refused-fence',release_digest=data_digest(probe.target['published_release']))
        except OperatorError:pass
        else:raise AssertionError('Native generic fence accepted populated recurrence')
    assert probe.sql("SELECT jsonb_build_object('state',state,'generation',generation,'release',release_digest) FROM mp_dispatch_control")==before
    result['native_generic_fence_refused_without_mutation']=True
    result['snapshot']=observed
    result['refused_fence_operation']=operation
    probe.sql("DELETE FROM mp_job_schedule WHERE public_id='"+result['schedule']+"'")
    result['synthetic_schedule_removed']=True
    write(path,result)
    print(json.dumps(dict(state='passed',tables=len(result['tables']),native_generic_fence_refused=True)))


if __name__=='__main__':run()
