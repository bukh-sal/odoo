"""Diagnose pending ORM authority reads; never replay the completed runner."""
import hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT))
from activate import context,j,f
state,record,native=context();assert state['phase']=='core10-pending-authority-01' and native.config['generation']==6
assert f.load(j.LOCAL/'core10-job-finish-01.json')['state']=='runner_completed_needs_probe'
retained=OUT/'job_native_attempt01.py';assert retained.exists() and retained.read_bytes()==(OUT/'job_native.py').read_bytes()
code='FIXTURE='+repr(f.load(j.LOCAL/'fixtures.json'))+'\nSEED='+repr(f.load(j.LOCAL/'core10-seed-01.json'))+'\nEXPECTED_DATABASE='+repr(state['active_db'])+'\n'+"""
import json
from odoo import api
from odoo.exceptions import AccessError
from odoo.addons.mp_identity.scopes import scoped_environment,current_scope
from odoo.addons.mp_core import job_dispatch as jobs
from odoo.addons.mp_core.dispatch import CallFrame
env.cr.rollback();assert env.cr.dbname==EXPECTED_DATABASE
env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);baseline=env.cr.fetchone()[0];assert baseline['state']=='completed' and baseline['attempts']==2
native=scoped_environment(api.Environment(env.cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['C']['public_id']);b=FIXTURE['bindings']['C']
native=native(context={**native.context,'_mp_call_frame':CallFrame(FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['public_id'],FIXTURE['site_id'],b['consumer_installation_id'],'org.example.notes',())})
env.cr.execute('SELECT m.id FROM mp_membership m JOIN mp_principal p ON p.id=m.principal_id WHERE p.public_id=%s AND m.workspace_id=%s',[FIXTURE['users']['alice']['principal_id'],FIXTURE['workspaces']['C']['id']]);ident=env.cr.fetchone()[0]
membership=env['mp.membership'].browse(ident);assert membership.role=='administrator'
membership.write({'role':'viewer'});assert membership.role=='viewer'
env.cr.execute('SELECT role FROM mp_membership WHERE id=%s',[ident]);sql_role=env.cr.fetchone()[0];assert sql_role=='administrator'
assert current_scope(native).role=='administrator'
native['mp.example.note'].browse([])._mp_guard('write')
assert jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key'])==SEED['job_id']
env.cr.execute('SELECT role FROM mp_membership WHERE id=%s',[ident]);assert env.cr.fetchone()[0]=='viewer'
# The enqueue's inner native savepoint flushes AFTER its SQL authorization.
# This is why the first minimal probe's later guard correctly denied.
membership.flush_recordset(['role'])
assert current_scope(native).role=='viewer'
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',SEED['job']['payload']['input'],SEED['key']);raise AssertionError('Flushed viewer allowed')
except AccessError:pass
try:native['mp.example.note'].browse([])._mp_guard('write');raise AssertionError('Flushed native viewer allowed')
except AccessError:pass
env.cr.rollback();env.invalidate_all()
env.cr.execute('SELECT role FROM mp_membership WHERE id=%s',[ident]);assert env.cr.fetchone()[0]=='administrator'
env.cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[SEED['job_id']]);assert env.cr.fetchone()[0]==baseline;env.cr.rollback()
print('MP_PENDING_AUTHORITY='+json.dumps(dict(result='confirmed_pending_ORM_authority_read_defect',ORM_role_after_write='viewer',SQL_and_scope_role_before_flush=sql_role,completed_job_retry_and_native_write_guard_accept_stale_role=True,explicit_flush_makes_both_deny=True,original_job_terminal_outcome_and_membership_exact_after_rollback=True,job_runner_replayed=False,required_fix='Flush relevant pending ORM identity/policy metadata before authoritative SQL scope reads; version mp_identity and qualify native batch/job paths before R1.')))
"""
raw=f.native(state,'core10-pending-authority-02',[],code);rows=[json.loads(l.split('MP_PENDING_AUTHORITY=',1)[1]) for l in raw.decode().splitlines() if l.startswith('MP_PENDING_AUTHORITY=')];assert len(rows)==1
f.save('pending-authority-counterexample.json',dict(**rows[0],image_id=state['image_id'],inventory_digest=state['inventory_digest'],original_probe_sha256=hashlib.sha256(retained.read_bytes()).hexdigest(),original_child_failed_after_prior_job_retry_assertions=True,already_passed=['real inventoried runner once-effect/originaluser/attempt2','original input/key/trace/deadline/budget retained','completed semantic retry saved result','changed-input conflict','failed new reservation absent while transaction live'],limits=['Committed revocations/current SQL policy remain denied; this newly exercised pending native ORM batch must also be supported.','No source/image/DB mutation committed by this counterexample. Earlier source role tests used direct SQL, so did not cover pending ORM metadata.']))
f.phase(state,'core10_pending_authority_defect_confirmed');f.guard(state)
print('Confirmed pending ORM role vs SQL scope discrepancy; explicit flush denies; native/job/role changes all rolled back, no runner replay.')
