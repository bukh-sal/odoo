"""Current installed reference profile still refuses unknown effects; all SQL rolls back."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from approve_runtime import ROOT,OUT,PRIVATE,context,op,base,f,j
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
state,native=context();assert f.load(PRIVATE/'remote-job.json')['state']=='verified' and native.config['generation']==23
before=base.snapshot(state,'image-success-unknown-guard-before');assert len(before['mp_job'])==30
helper=ReferenceDispatchMaintenance(native);policy=helper.reference_policy(native.config)
assert policy['profile']=='r1-reference-stateless-v1'
from modular_platform.plans import data_digest
payload=dict(site_id=state['site_id'],database=state['active_db'],release_digest=data_digest(native.config['published_release']),reference=policy)
code="""import configparser,json,sys,uuid
import psycopg2
from modular_platform import dispatch_lifecycle as LC
v=json.load(sys.stdin);config=configparser.RawConfigParser();config.read('/run/secrets/odoo_config');o=config['options']
connection=psycopg2.connect(host=o['db_host'],port=o.get('db_port','5432'),user=o['db_user'],password=o['db_password'],dbname=v['database'])
scope=LC.LifecycleScope(v['site_id'],v['release_digest'],reference=v['reference'])
try:
 with connection.cursor() as cr:
  cr.execute("SET LOCAL statement_timeout='10s'; SET LOCAL lock_timeout='5s'")
  before=LC.observe(cr,scope)
  assert before['control']['state']=='enabled' and before['uncertain_jobs']==0
  LC.fence(cr,scope,str(uuid.uuid4()))
  cr.execute("UPDATE mp_job SET state='outcome_unknown',effect_mode='reconcile',effect_started=true,result=NULL,finished_at=NULL WHERE id=(SELECT min(id) FROM mp_job WHERE state='completed') RETURNING public_id")
  job=cr.fetchone()[0];unknown=LC.observe(cr,scope)
  assert unknown['job_states']['outcome_unknown']==1 and unknown['uncertain_jobs']==1
  try:LC.enable(cr,scope,unknown['state_digest'])
  except LC.DispatchLifecycleError as exc:
   assert str(exc)=='Unreconciled effects or credentials prevent native dispatch resume'
  else:raise AssertionError('Current external profile resumed unknown effect')
 connection.rollback()
 with connection.cursor() as cr:assert LC.observe(cr,scope)==before
 connection.rollback()
 print(json.dumps(dict(result='passed_installed_current_profile_unknown_effect_refusal',profile=v['reference']['profile'],job_id=job,rollback_restored_exact_native_dispatch_state=True)))
finally:connection.rollback();connection.close()
"""
result=json.loads(f.command('image-success-installed-unknown-guard',['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','-c',code],input=json.dumps(payload).encode()))
assert result['result']=='passed_installed_current_profile_unknown_effect_refusal'
assert base.snapshot(state,'image-success-unknown-guard-after')==before
result.update(all30jobs_other17tables_exact=True,no_external_effect_or_job_dispatch=True,
    limits='Rollback-only current guard regression. Actual non-idempotent effect/crash/lease/nonretry evidence remains job03-01.')
f.save('unknown-effect-refusal.json',result)
print('Installed current default external profile refuses unknown effect; rollback restores all30jobs/control/data exactly',flush=True)
