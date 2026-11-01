"""Rollback-only real PostgreSQL release/history and receipt counterexamples."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='event_jobs_regression_verified'
f.OUTPUT=OUT
source="""import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events
from modular_platform import durable,event_store as store
env.cr.rollback()
fixture=json.loads(FIXTURE_JSON)
query=\"SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'events',(SELECT count(*) FROM mp_outbox),'notes',(SELECT count(*) FROM mp_example_note),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'deliveries',(SELECT count(*) FROM mp_event_delivery),'consumptions',(SELECT count(*) FROM mp_event_consumption),'consumer_states',(SELECT count(*) FROM mp_event_consumer_state),'control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c));\"
env.cr.execute(query);before=env.cr.fetchone()[0]
env.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.site_id'\");site=env.cr.fetchone()[0];assert site==fixture['site_id']
env.cr.execute(\"SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'\");release=env.cr.fetchone()[0]
durable.set_control(env.cr,site,release,'enabled')
native=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['A']['public_id'])
def call(kind,**values):return events.dispatch(native,dict(protocol=1,kind=kind+'_request',request_id=str(uuid4()),**values),binding_id=fixture['bindings']['A']['binding_id'])
sub=call('subscribe',topic='org.example.notes.changed',idempotency_key=str(uuid4()))['subscription_id']
note=native['mp.example.note'].create(dict(title='Rollback-only lifecycle counterexample'));native.flush_all()
env.cr.execute('SELECT to_jsonb(s) FROM mp_event_subscription s WHERE public_id=%s',[sub]);subscription=env.cr.fetchone()[0]
old=store.candidates(env.cr,subscription,50);assert note.public_id in [e['aggregate_id'] for e in old]
next_release='sha256:'+'f'*64;assert next_release!=release
hidden=store.candidates(env.cr,dict(subscription,release_digest=next_release),50)
assert note.public_id not in [e['aggregate_id'] for e in hidden]
batch=call('poll',subscription_id=sub,limit=50)['deliveries'];target=next(d for d in batch if d['event']['aggregate_id']==note.public_id)
receipt=dict(delivery_id=target['id'],receipt=target['receipt'],generation=target['generation'])
old_generation=durable.control(env.cr,site,release)
durable.set_control(env.cr,site,release,'paused');new_generation=durable.set_control(env.cr,site,release,'enabled');assert new_generation>old_generation
ack=call('ack',subscription_id=sub,receipts=[receipt]);assert ack['acknowledged']==[target['id']]
env.cr.rollback();env.cr.execute(query);after=env.cr.fetchone()[0];assert before==after;env.cr.rollback()
print('MP_DISPATCH_COUNTEREXAMPLES='+json.dumps(dict(result='confirmed_required_defects',compatible_release_candidate_query_hides_retained_event=True,pause_resume_accepts_obsolete_event_receipt=True,synthetic_transaction_rolled_back=True,protected_row_counts_and_control_exact=after,real_upgrade_or_restore_exercised=False)))
"""
code='FIXTURE_JSON='+repr((j.LOCAL/'fixtures.json').read_text())+'\n'+source
marker=j.LOCAL/'dispatch-counterexamples-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
raw=f.native(state,'dispatch-counterexamples-01',[],code)
rows=[json.loads(line.split('MP_DISPATCH_COUNTEREXAMPLES=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_DISPATCH_COUNTEREXAMPLES=')];assert len(rows)==1
result=dict(**rows[0],image_id=state['image_id'],inventory_digest=state['inventory_digest'],project=state['project'])
f.save('counterexamples.json',result);f.write(marker,dict(state='completed',**result));f.phase(state,'dispatch_counterexamples_verified');f.guard(state)
print(json.dumps(dict(result=result['result'],rollback_exact=True)))
