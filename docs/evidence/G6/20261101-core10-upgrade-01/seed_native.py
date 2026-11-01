"""One original-user claimed job, enqueued after approval before native drain."""
import json
from dataclasses import asdict,replace
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events,job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
env.cr.rollback();assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute('SELECT state,generation FROM mp_dispatch_control');assert env.cr.fetchone()==('enabled',28)
env.cr.execute('SELECT count(*) FROM mp_job');assert env.cr.fetchone()[0]==4
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
binding=FIXTURE['bindings']['C'];frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame})
subscription=events.dispatch(native,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=binding['binding_id'])['subscription_id']
note=native['mp.example.note'].create(dict(title='Core10  compatible  native job',body='Owned populated core upgrade fixture'));native.flush_all()
definition=jobs.DEFINITIONS[('org.example.notes:normalize_title',1)];assert definition.timeout_seconds==120
# Explicit trusted fixture scheduling policy, never a refill of stored work.
jobs.DEFINITIONS[(definition.ident,1)]=replace(definition,timeout_seconds=3600)
key=uuid4().hex;trace=str(uuid4());ident=jobs.enqueue_bound(native,'documents',definition.ident,dict(note_id=note.public_id,expected_revision=1),key,request_id=trace)
invocation=jobs.prepare_one(env,str(uuid4()),lease_seconds=300);assert invocation.claim.job_id==ident
batch=events.dispatch(native,dict(protocol=1,kind='poll_request',request_id=str(uuid4()),subscription_id=subscription,limit=50),binding_id=binding['binding_id'])['deliveries']
target=next(d for d in batch if d['event']['aggregate_id']==note.public_id)
env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident]);row=env.cr.fetchone()[0];assert row['state']=='running' and row['attempts']==1
env.cr.execute('SELECT to_jsonb(o) FROM mp_outbox o WHERE workspace_id=%s ORDER BY id',[FIXTURE['workspaces']['C']['id']]);history=[r[0] for r in env.cr.fetchall()]
assert any(r['aggregate_id']==PRIOR_NOTE and r['aggregate_sequence']==1 for r in history)
env.cr.commit()
print('MP_CORE10_SEED='+json.dumps(dict(job_id=ident,note_id=note.public_id,key=key,trace=trace,job=row,invocation=asdict(invocation),computed=jobs.compute(invocation),subscription_id=subscription,receipt=dict(delivery_id=target['id'],receipt=target['receipt'],generation=target['generation']),history=history,prior_note=PRIOR_NOTE,fixture_timeout_seconds=3600,production_timeout_seconds=120)))
