"""Owned durable native claim and receipt; original budgets survive recovery."""
import json
from dataclasses import asdict,replace
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events,job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame

env.cr.rollback()
assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute('SELECT state,generation FROM mp_dispatch_control')
assert env.cr.fetchone()==('enabled',21)
env.cr.execute('SELECT count(*) FROM mp_job');assert env.cr.fetchone()[0]==3
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
binding=FIXTURE['bindings']['C']
frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame})
subscription=events.dispatch(native,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=binding['binding_id'])['subscription_id']
note=native['mp.example.note'].create(dict(title='Owned  restored  native job',body='Bounded native recovery fixture; preserve this row'))
native.flush_all()
key=uuid4().hex;trace=str(uuid4())
# Trusted test scheduling policy only in this one short-lived process. Keep the
# actual registered handler/version/schema/permissions/effect unchanged. The
# production enqueue default stays120s. Never refill a stored budget later.
definition=jobs.DEFINITIONS[('org.example.notes:normalize_title',1)]
assert definition.timeout_seconds==120
jobs.DEFINITIONS[(definition.ident,1)]=replace(definition,timeout_seconds=3600)
ident=jobs.enqueue_bound(native,'documents',definition.ident,dict(note_id=note.public_id,expected_revision=1),key,request_id=trace)
invocation=jobs.prepare_one(env,str(uuid4()),lease_seconds=300)
assert invocation.claim.job_id==ident
computed=jobs.compute(invocation)
batch=events.dispatch(native,dict(protocol=1,kind='poll_request',request_id=str(uuid4()),subscription_id=subscription,limit=50),binding_id=binding['binding_id'])['deliveries']
target=next(d for d in batch if d['event']['aggregate_id']==note.public_id)
env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident]);row=env.cr.fetchone()[0]
assert row['state']=='running' and row['attempts']==1 and row['max_attempts']==5
env.cr.commit()
print('MP_NATIVE_RECOVERY_SEED='+json.dumps(dict(note_id=note.public_id,job_id=ident,key=key,trace=trace,invocation=asdict(invocation),computed=computed,job=row,subscription_id=subscription,receipt=dict(delivery_id=target['id'],receipt=target['receipt'],generation=target['generation']),fixture_timeout_seconds=3600,production_timeout_seconds=120)))
