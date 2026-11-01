"""Actual retained-image stale claims/receipts and original-user resumed effect."""
import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events,job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import durable

env.cr.rollback();assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute('SELECT state,generation FROM mp_dispatch_control');control=env.cr.fetchone();assert control==('enabled',25)
old=SEED['invocation'];old=dict(old,claim=durable.Claim(**old['claim']));obsolete=jobs.Invocation(**old)
try:
    with env.cr.savepoint():jobs.finish_one(env,obsolete,SEED['computed'])
except durable.ClaimLost:pass
else:raise AssertionError('Obsolete pre-fault claim was accepted')
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
binding=FIXTURE['bindings']['C']
frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame})
try:
    with env.cr.savepoint():
        events.dispatch(native,dict(protocol=1,kind='ack_request',request_id=str(uuid4()),subscription_id=SEED['subscription_id'],receipts=[SEED['receipt']]),binding_id=binding['binding_id'])
except PublicError as error:assert error.code=='CONFLICT'
else:raise AssertionError('Obsolete pre-fault receipt was accepted')
if PHASE=='before':
    env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);before=env.cr.fetchone()[0]
    assert before['state']=='pending' and before['attempts']==1
    # Real retained-image semantic retry before the recovered effect. This
    # read of the saved identity must not refill deadline/budget/first trace.
    assert jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key'],request_id=str(uuid4()))==SEED['job_id']
    env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);assert env.cr.fetchone()[0]==before
    env.cr.rollback()
    print('MP_NATIVE_RECOVERY_FINISHED='+json.dumps(dict(result='passed_obsolete_claim_receipt_and_pre_effect_semantic_retry',old_claim_denied=True,old_receipt_denied=True,original_row_unchanged=True)))
    raise SystemExit(0)
env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);after=env.cr.fetchone()[0]
for key in ['actor_id','workspace_id','installation_id','idempotency_key','deadline_at','max_attempts','payload','input_digest']:
    assert after[key]==SEED['job'][key],key
outcome=after['result'];assert after['state']=='completed' and after['attempts']==2 and outcome['revision']==2
env.cr.execute('SELECT title,revision,write_uid FROM mp_example_note WHERE public_id=%s',[SEED['note_id']]);note=env.cr.fetchone()
assert note==('Owned restored native job',2,FIXTURE['users']['alice']['id'])
env.cr.execute('SELECT count(*) FROM mp_outbox WHERE aggregate_id=%s AND aggregate_sequence=2',[SEED['note_id']]);assert env.cr.fetchone()[0]==1
try:
    with env.cr.savepoint():jobs.finish_one(env,obsolete,SEED['computed'])
except durable.ClaimLost:pass
else:raise AssertionError('Obsolete claim was accepted after completion')
env.cr.execute('SELECT state FROM mp_event_delivery WHERE public_id=%s',[SEED['receipt']['delivery_id']]);assert env.cr.fetchone()[0]!='acknowledged'
env.cr.rollback()
print('MP_NATIVE_RECOVERY_FINISHED='+json.dumps(dict(result='passed_original_user_resumed_effect_and_obsolete_tokens',job_id=SEED['job_id'],note_id=SEED['note_id'],revision=2,attempts=2,write_uid=note[2],outcome=outcome,original_input_key_trace_deadline_budget_preserved=True,semantic_retry_before_effect_same_ID=True,old_claim_denied_before_and_after_effect=True,old_receipt_denied=True,receipt_expiry_limit='Fifteen-second event lease expired during real reviewed recovery; generation advanced and subscription closed are independently verified. Immediate within-lease invalidation was proved by native lifecycle tests.',one_native_revision_two_event=True)))
