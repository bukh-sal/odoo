"""Discriminate completed semantic retry before implementing job carry-forward."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'docs/evidence/G6/20261029-events-01'))
import fixture as j
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state);assert state['phase']=='dispatch_history_source_verified'
code='FIXTURE_JSON='+repr((j.LOCAL/'fixtures.json').read_text())+'\n'+"""
import json
from uuid import uuid4
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core import job_dispatch as jobs
from odoo.addons.mp_core.controllers import PublicError
from odoo.addons.mp_core.dispatch import CallFrame
from modular_platform import durable
env.cr.rollback();fixture=json.loads(FIXTURE_JSON)
query="SELECT jsonb_build_object('jobs',(SELECT count(*) FROM mp_job),'notes',(SELECT count(*) FROM mp_example_note),'events',(SELECT count(*) FROM mp_outbox),'control',(SELECT jsonb_agg(to_jsonb(c)) FROM mp_dispatch_control c));"
env.cr.execute(query);before=env.cr.fetchone()[0]
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=env.cr.fetchone()[0];site=fixture['site_id'];durable.set_control(env.cr,site,release,'enabled')
env.cr.execute("SELECT public_id FROM mp_plugin_installation WHERE plugin_id='org.example.notes'");consumer=env.cr.fetchone()[0]
frame=CallFrame(fixture['users']['alice']['principal_id'],fixture['workspaces']['A']['public_id'],site,consumer,'org.example.notes',())
native=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['A']['public_id']);native=native(context={**native.context,'_mp_call_frame':frame})
note=native['mp.example.note'].create(dict(title='Completed   semantic  retry'));values=dict(note_id=note.public_id,expected_revision=1);key=uuid4().hex
ident=jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',values,key)
invocation=jobs.prepare_one(env,str(uuid4()));assert invocation.claim.job_id==ident
outcome=jobs.finish_one(env,invocation,jobs.compute(invocation));assert outcome['revision']==2
try:jobs.enqueue_bound(native,'documents','org.example.notes:normalize_title',values,key);raise AssertionError('Expected stored-revision preflight counterexample')
except PublicError as error:assert error.code=='CONFLICT'
env.cr.rollback();env.cr.execute(query);assert env.cr.fetchone()[0]==before;env.cr.rollback()
print('MP_JOB_REPEAT_COUNTEREXAMPLE='+json.dumps(dict(result='confirmed_required_defect',same_key_same_input_completed_job_refused_by_stale_preflight=True,business_and_control_rollback_exact=True,lease_reclaim_or_obsolete_claim_proof_contradicted=False)))
"""
marker=j.LOCAL/'dispatch-job-repeat-counterexample-01.json';assert not marker.exists();f.write(marker,dict(state='running'))
raw=f.native(state,'dispatch-job-repeat-counterexample-01',[],code)
rows=[json.loads(line.split('MP_JOB_REPEAT_COUNTEREXAMPLE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_JOB_REPEAT_COUNTEREXAMPLE=')];assert len(rows)==1
result=dict(**rows[0],image_id=state['image_id'],required_fix='Check an authorized saved semantic job before new-work revision preflight; retain current actor/resource/binding checks and reject changed input. Qualify before carry-forward is complete.')
f.write(marker,dict(state='completed',**result));f.save('job-repeat-counterexample.json',result);f.phase(state,'dispatch_job_repeat_defect_verified');f.guard(state);print('Completed-job semantic repeat counterexample confirmed; rollback exact.')
