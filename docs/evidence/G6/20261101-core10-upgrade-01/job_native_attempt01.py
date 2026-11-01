"""Installed core10 adapter checks; no source substitution in this process."""
import json
from uuid import uuid4
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import events,job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
from odoo.addons.mp_core.controllers import PublicError
from modular_platform import durable
env.cr.rollback();assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute('SELECT state,generation FROM mp_dispatch_control');assert env.cr.fetchone()==('enabled',31)
old=dict(SEED['invocation'],claim=durable.Claim(**SEED['invocation']['claim']));obsolete=jobs.Invocation(**old)
try:
    with env.cr.savepoint():jobs.finish_one(env,obsolete,SEED['computed'])
except durable.ClaimLost:pass
else:raise AssertionError('Obsolete pre-upgrade claim accepted')
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id'])
binding=FIXTURE['bindings']['C'];frame=CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['public_id'],FIXTURE['site_id'],binding['consumer_installation_id'],'org.example.notes',())
native=native(context={**native.context,'_mp_call_frame':frame})
try:
    with env.cr.savepoint():events.dispatch(native,dict(protocol=1,kind='ack_request',request_id=str(uuid4()),subscription_id=SEED['subscription_id'],receipts=[SEED['receipt']]),binding_id=binding['binding_id'])
except PublicError as error:assert error.code=='CONFLICT'
else:raise AssertionError('Obsolete pre-upgrade event receipt accepted')
env.cr.execute('SELECT %s::timestamp>timezone(\'UTC\',clock_timestamp())',[SEED['job']['lease_until']]);old_lease_live=env.cr.fetchone()[0]
def row():
    env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);return env.cr.fetchone()[0]
baseline=row()
if PHASE=='before':
    assert baseline['state']=='pending' and baseline['attempts']==1
    assert jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key'],request_id=str(uuid4()))==SEED['job_id']
    assert row()==baseline;env.cr.rollback()
    print('MP_CORE10_JOB='+json.dumps(dict(result='passed_pre_effect_old_claim_receipt_and_semantic_retry',old_claim_denied=True,old_receipt_denied=True,old_claim_still_within_original_lease=old_lease_live,original_job_row_exact=True)))
    raise SystemExit(0)
assert baseline['state']=='completed' and baseline['attempts']==2 and baseline['result']['revision']==2
for key in ['actor_id','workspace_id','installation_id','payload','input_digest','idempotency_key','max_attempts','deadline_at']:
    assert baseline[key]==SEED['job'][key],key
env.cr.execute('SELECT title,revision,write_uid FROM mp_example_note WHERE public_id=%s',[SEED['note_id']]);assert env.cr.fetchone()==('Core10 compatible native job',2,FIXTURE['users']['alice']['id'])
env.cr.execute('SELECT count(*) FROM mp_outbox WHERE aggregate_id=%s AND aggregate_sequence=2',[SEED['note_id']]);assert env.cr.fetchone()[0]==1
# This was the real old-image counterexample: revision1 input after its own
# completed revision2 effect must return the saved identity/outcome/first trace.
assert jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key'],request_id=str(uuid4()))==SEED['job_id']
assert jobs.status(native,SEED['job_id'])['result']==baseline['result'] and row()==baseline
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=SEED['note_id'],expected_revision=2),SEED['key'])
except (durable.QueueError,PublicError):pass
else:raise AssertionError('Changed input accepted under old semantic key')
assert row()==baseline
failed_key=uuid4().hex
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=SEED['note_id'],expected_revision=999999),failed_key)
except PublicError as error:assert error.code=='CONFLICT'
else:raise AssertionError('New stale revision was accepted')
env.cr.execute('SELECT count(*) FROM mp_job WHERE idempotency_key=%s',[failed_key]);assert env.cr.fetchone()[0]==0
env.cr.execute('SELECT m.id FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id WHERE p.public_id=%s AND m.workspace_id=%s',[FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['id']]);membership=env['mp.membership'].browse(env.cr.fetchone()[0]);assert membership.role=='administrator'
membership.write(dict(role='viewer'))
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key'])
except (AccessError,PublicError):pass
else:raise AssertionError('Completed replay bypassed current actor role')
env.cr.rollback();env.invalidate_all();assert row()==baseline
env.cr.execute('SELECT role FROM mp_membership WHERE id=%s',[membership.id]);assert env.cr.fetchone()[0]=='administrator'
env.cr.rollback()
print('MP_CORE10_JOB='+json.dumps(dict(result='passed_installed_core10_original_user_effect_and_completed_retry',revision=2,attempts=2,original_user_id=FIXTURE['users']['alice']['id'],one_native_revision_event=True,original_input_key_trace_deadline_budget_preserved=True,old_claim_and_receipt_denied=True,old_claim_still_within_original_lease=old_lease_live,completed_semantic_retry_saved_outcome_and_first_trace=True,changed_input_conflict=True,failed_new_work_reservation_absent_in_live_transaction=True,current_role_rechecked_for_completed_retry=True,all_negative_fixture_changes_rolled_back=True,source_substitution=False)))
