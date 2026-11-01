"""Corrected semantic retry source on native PG, rollback-only five scenarios."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='dispatch_job_repeat_defect_verified'
store=ROOT/'packages/platform_sdk/modular_platform/durable.py';jobs=ROOT/'platform_addons/mp_core/job_dispatch.py'
marker=j.LOCAL/'dispatch-job-repeat-source-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
code="import json,sys,types\nfrom uuid import uuid4\nfrom odoo import api\nfrom odoo.exceptions import AccessError\nfrom odoo.addons.mp_identity.scopes import scoped_environment\nfrom odoo.addons.mp_core import job_dispatch as original\nfrom odoo.addons.mp_core.dispatch import CallFrame\nfrom odoo.addons.mp_core.controllers import PublicError\nenv.cr.rollback()\n"
code+="store=types.ModuleType('modular_platform.durable_probe');store.__package__='modular_platform';sys.modules[store.__name__]=store\nexec(compile("+repr(store.read_text())+",'durable_probe','exec'),store.__dict__)\n"
code+="jobs=types.ModuleType('odoo.addons.mp_core.job_dispatch_probe');jobs.__package__='odoo.addons.mp_core';sys.modules[jobs.__name__]=jobs\nexec(compile("+repr(jobs.read_text())+",'job_dispatch_probe','exec'),jobs.__dict__);jobs.durable=store;jobs.DEFINITIONS=original.DEFINITIONS.copy()\n"
code+='fixture=json.loads('+repr((j.LOCAL/'fixtures.json').read_text())+')\n'+"""
query="SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'notes',(SELECT count(*) FROM mp_example_note),'events',(SELECT count(*) FROM mp_outbox),'control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c));"
env.cr.execute(query);before=env.cr.fetchone()[0]
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=env.cr.fetchone()[0];site=fixture['site_id'];store.set_control(env.cr,site,release,'enabled')
env.cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes'");consumer=env.cr.fetchone()[0]
frame=CallFrame(fixture['users']['alice']['principal_id'],fixture['workspaces']['A']['public_id'],site,consumer,'org.example.notes',())
native=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['A']['public_id']);native=native(context={**native.context,'_mp_call_frame':frame})
note=native['mp.example.note'].create(dict(title='Completed   semantic  retry'));values=dict(note_id=note.public_id,expected_revision=1);key=uuid4().hex;first=str(uuid4());second=str(uuid4())
ident=jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',values,key,request_id=first)
invocation=jobs.prepare_one(env,str(uuid4()));assert invocation.claim.job_id==ident
outcome=jobs.finish_one(env,invocation,jobs.compute(invocation));assert outcome['revision']==2
assert jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',values,key,request_id=second)==ident
assert jobs.status(native,ident)['result']==outcome
env.cr.execute('SELECT payload FROM mp_job WHERE public_id=%s',[ident]);assert env.cr.fetchone()[0]['context']['request_id']==first
# Changed input cannot join the saved result, even for another authorized Note.
other=native['mp.example.note'].create(dict(title='Other owned retry target'))
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=other.public_id,expected_revision=1),key);raise AssertionError('Changed input joined saved result')
except store.QueueError:pass
# A newly inserted reservation is removed when its revision preflight fails.
badkey=uuid4().hex
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',dict(note_id=other.public_id,expected_revision=9),badkey);raise AssertionError('Bad revision accepted')
except PublicError as error:assert error.code=='CONFLICT'
env.cr.execute('SELECT count(*) FROM mp_job WHERE idempotency_key=%s',[badkey]);assert env.cr.fetchone()[0]==0
# Current role still controls saved outcomes: no administrator fallback.
env.cr.execute("UPDATE mp_membership SET role='viewer' WHERE principal_id=(SELECT id FROM mp_principal WHERE public_id=%s) AND workspace_id=%s",[fixture['users']['alice']['principal_id'],fixture['workspaces']['A']['id']])
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',values,key);raise AssertionError('Viewer obtained saved write job')
except AccessError:pass
env.cr.rollback();env.cr.execute(query);assert env.cr.fetchone()[0]==before;env.cr.rollback()
print('MP_JOB_REPEAT_SOURCE='+json.dumps(dict(result='passed',scenarios=5,completed_same_key_returns_original_job_and_result=True,first_trace_preserved=True,changed_input_refused=True,failed_new_preflight_reservation_rolled_back=True,current_role_rechecked=True,all_fixture_writes_rolled_back=True,immutable_deployment=False)))
"""
raw=f.native(state,'dispatch-job-repeat-source-01',[],code)
rows=[json.loads(line.split('MP_JOB_REPEAT_SOURCE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_JOB_REPEAT_SOURCE=')];assert len(rows)==1
result=dict(**rows[0],backend_image=state['image_id'],source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [store,jobs]},limits=['Corrected source in short-lived native process; normal immutable upgrade/current job authorization and actual runner regression remain required.'])
f.write(marker,dict(state='completed',**result));f.save('job-repeat-source.json',result);f.phase(state,'dispatch_job_repeat_source_verified');f.guard(state);print('Five corrected-source native job retry checks passed; rollback exact.')
