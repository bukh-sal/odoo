"""Exercise corrected candidate/replay source on native PG without deployment."""
import argparse,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='dispatch_fence_verified'
parser=argparse.ArgumentParser();parser.add_argument('--label',default='history-source-01');args=parser.parse_args();assert re.fullmatch('[a-z0-9-]{1,35}',args.label)
store=ROOT/'packages/platform_sdk/modular_platform/event_store.py';gateway=ROOT/'platform_addons/mp_core/events.py'
marker=j.LOCAL/('dispatch-'+args.label+'.json');assert not marker.exists();f.write(marker,dict(state='running'))
code="import ast,json,sys,types\nfrom uuid import uuid4\nfrom odoo import api\nfrom odoo.addons.mp_identity.scopes import scoped_environment\nfrom odoo.addons.mp_core import events as original\nfrom modular_platform import durable\nenv.cr.rollback()\n"
code+="store=types.ModuleType('modular_platform.event_store_probe');store.__package__='modular_platform';sys.modules[store.__name__]=store\nexec(compile("+repr(store.read_text())+",'event_store_probe','exec'),store.__dict__)\n"
code+="gateway=types.ModuleType('odoo.addons.mp_core.events_probe');gateway.__package__='odoo.addons.mp_core';sys.modules[gateway.__name__]=gateway\ntree=ast.parse("+repr(gateway.read_text())+");tree.body=[node for node in tree.body if not isinstance(node,ast.ClassDef) or node.name!='EventGateway']\nexec(compile(tree,'events_probe','exec'),gateway.__dict__);gateway.store=store;gateway.TOPICS=original.TOPICS.copy();gateway.CONSUMERS=original.CONSUMERS.copy()\n"
code+='fixture=json.loads('+repr((j.LOCAL/'fixtures.json').read_text())+')\n'
code+="""
query="SELECT jsonb_build_object('notes',(SELECT count(*) FROM mp_example_note),'events',(SELECT count(*) FROM mp_outbox),'subscriptions',(SELECT count(*) FROM mp_event_subscription),'deliveries',(SELECT count(*) FROM mp_event_delivery),'control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c),'release',(SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'));"
env.cr.execute(query);before=env.cr.fetchone()[0];site=fixture['site_id'];release=before['release']
durable.set_control(env.cr,site,release,'enabled')
native=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['A']['public_id'])
note=native['mp.example.note'].create(dict(title='Compatible history source proof'));native.flush_all();ident=note.public_id
env.cr.execute('SELECT public_id,release_digest FROM mp_outbox WHERE aggregate_id=%s',[ident]);event,original_release=env.cr.fetchone();assert original_release==release
next_release='sha256:'+'e'*64;assert next_release!=release
env.cr.execute("UPDATE ir_config_parameter SET value=%s WHERE key='mp.release_digest'",[next_release]);durable.set_control(env.cr,site,next_release,'enabled')
def call(kind,**values):return gateway.dispatch(native,dict(protocol=1,kind=kind+'_request',request_id=str(uuid4()),**values),binding_id=fixture['bindings']['A']['binding_id'])
sub=call('subscribe',topic='org.example.notes.changed',idempotency_key=str(uuid4()))['subscription_id']
batch=call('poll',subscription_id=sub,limit=50)['deliveries'];target=next(d for d in batch if d['event']['id']==event)
assert target['event']['payload']==dict(note_id=ident,revision=1,change='created')
receipt=dict(delivery_id=target['id'],receipt=target['receipt'],generation=target['generation']);call('ack',subscription_id=sub,receipts=[receipt])
call('replay',subscription_id=sub,event_ids=[event]);again=call('poll',subscription_id=sub,limit=50)['deliveries'];assert any(d['event']['id']==event for d in again)
env.cr.execute('SELECT release_digest FROM mp_outbox WHERE public_id=%s',[event]);assert env.cr.fetchone()[0]==original_release
# Same-topic syntax cannot widen scope: a new B stream cannot replay A history.
native_b=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['B']['public_id'])
b=gateway.dispatch(native_b,dict(protocol=1,kind='subscribe_request',request_id=str(uuid4()),topic='org.example.notes.changed',idempotency_key=str(uuid4())),binding_id=fixture['bindings']['B']['binding_id'])['subscription_id']
try:gateway.dispatch(native_b,dict(protocol=1,kind='replay_request',request_id=str(uuid4()),subscription_id=b,event_ids=[event]));raise AssertionError('Foreign replay allowed')
except gateway.PublicError as error:assert error.code=='NOT_FOUND'
durable.set_control(env.cr,site,next_release,'paused')
assert call('close',subscription_id=sub)==call('close',subscription_id=sub)
assert call('status',subscription_id=sub)['state']=='closed'
env.cr.rollback();env.cr.execute(query);assert env.cr.fetchone()[0]==before;env.cr.rollback()
print('MP_HISTORY_SOURCE='+json.dumps(dict(result='passed',retained_candidate_and_replay_across_compatible_release=True,original_producer_release_immutable=True,cross_workspace_replay_refused=True,paused_close_idempotent_and_status_safe=True,transaction_rollback_exact=True,actual_immutable_upgrade=False)))
"""
try:raw=f.native(state,'dispatch-'+args.label,[],code)
except AssertionError:raise AssertionError('Inspect retained private source-history process/logs before continuation') from None
rows=[json.loads(line.split('MP_HISTORY_SOURCE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_HISTORY_SOURCE=')];assert len(rows)==1
result=dict(**rows[0],backend_image=state['image_id'],source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [store,gateway]},limits=['Corrected source evaluated in short-lived native process; no endpoint or deployed image patched. Real controlled upgrade/history proof remains required.'])
f.write(marker,dict(state='completed',**result));f.save('history-source.json' if args.label=='history-source-01' else args.label+'.json',result);f.phase(state,'dispatch_history_source_verified');f.guard(state);print('Compatible history source, paused close and scope checks passed; rollback exact.')
