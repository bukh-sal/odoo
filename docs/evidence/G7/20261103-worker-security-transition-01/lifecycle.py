"""Ordinary reviewed metadata lifecycle on the populated core21 deployment."""
import argparse,copy,hashlib,importlib.util,json,sys,tarfile
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=module('worker_security_core21',OUT.parent/'20261103-core21-maintenance-01/activate.py')
prior=module('worker_security_old_client',ROOT/'docs/evidence/G6/20261102-worker-image-upgrade-01/suspend.py')
f,j=base.f,base.j;f.OUTPUT=OUT
from modular import configuration
from modular_platform.metadata_executor import ReferenceMetadataExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.contracts import validate_operations_view
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
PRIVATE=j.LOCAL/'worker-security-transition-01'
def context():
 state=f.load(j.LOCAL/'state.json');f.guard(state)
 native=ReferenceMetadataExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
 assert native.config['image_id']==base.IMAGE
 return state,native
def path(action):return PRIVATE/(action+'.json')
def phase(r,value,action):r['state']=value;f.write(path(action),r)
def client(state,actor='operator'):return prior.client(state,actor)
def prepare(action):
 state,native=context();assert native.config['generation']==(31 if action=='enable' else 30)
 if not PRIVATE.exists():assert action=='suspend';protect_directory(PRIVATE)
 assert not path(action).exists()
 if action=='upgrade':assert f.load(PRIVATE/'runtime.json')['state']=='published_new_image'
 if action=='enable':assert f.load(path('upgrade'))['state']=='verified'
 scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope']
 before=base.snapshot(state,'worker-security-'+action+'-before')
 assert len(before['mp_job'])==37 and all(r['state'] in ('completed','dead_letter','cancelled') for r in before['mp_job'])
 assert not any(r['state']=='leased' for r in before['mp_event_delivery'])
 f.write(PRIVATE/(action+'-before.json'),before)
 f.write(PRIVATE/(action+'-worker-before.json'),base.worker(native,'worker-security-'+action+'-worker-before'))
 f.write(PRIVATE/(action+'-schema-before.json'),dict(digest=base.schema(state,'worker-security-'+action+'-schema-before')))
 f.write(PRIVATE/(action+'-modules-before.json'),json.loads(f.sql(state,'worker-security-'+action+'-modules-before','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;')))
 r=dict(scope=scope,base_generation=native.config['generation']);phase(r,'requesting',action)
 c=client(state);nomination=dict(schema_version=1,operation='prepare',operation_type=action,plugin_id='org.example.document_stats',site_id=scope['site_id'],workspace_ids=[scope['workspace_id']],cascade=False)
 if action=='upgrade':
  metadata=f.load(PRIVATE/'metadata.json');nomination.update(artifact_version=metadata['version'],artifact_digest=metadata['digest'])
 code,response=c.request('/api/v1/operations/prepare',nomination,headers={'X-CSRFToken':c.csrf});assert code==200,(code,response)
 view=validate_operations_view(response['data']);assert view['targets']==[dict(**scope,plugin_id='org.example.document_stats',action=action)]
 assert view['restart_required'] and not view['native_trusted_code']
 r.update(operation_id=view['operation_id'],plan_hash=view['plan_hash']);phase(r,'prepared',action);f.save(action+'-preview.json',view)
 code,response=c.request('/api/v1/operations/request',dict(schema_version=1,operation='request',operation_id=r['operation_id'],plan_hash=r['plan_hash'],request_id=str(uuid4())),headers={'X-CSRFToken':c.csrf});assert code==200
 code,response=c.request('/api/v1/operations/bundle/'+r['operation_id']);assert code==200;bundle=response['data'];f.save(action+'-bundle.json',bundle)
 assert bundle['plan_hash']==r['plan_hash'] and bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes']
 assert base.snapshot(state,'worker-security-'+action+'-after-request')==before
 phase(r,'manager_requested',action);print(action+': ordinary populated manager request prepared',flush=True)
def approve(action):
 state,native=context();r=f.load(path(action));assert r['state']=='manager_requested'
 ops=base.base.prefix()+['operations','--store',str(native.store.root)]
 phase(r,'importing_and_reviewing',action)
 f.save(action+'-import.json',json.loads(f.command('worker-security-'+action+'-import',ops+['import-request',r['operation_id']]+base.base.validation(native))))
 review=native.store.review(r['operation_id'],native._validate());assert review['plan_hash']==r['plan_hash'];f.save(action+'-review.json',review)
 native._runtime_preflight(native.store.bundle(r['operation_id']))
 f.command('worker-security-'+action+'-approve',ops+['approve',r['operation_id'],'--plan-hash',r['plan_hash'],'--noninteractive','--ack-trust']+base.base.validation(native))
 phase(r,'approved',action);print(action+': independently reconstructed/reviewed/exact approved',flush=True)
def apply(action):
 state,native=context();r=f.load(path(action));assert r['state']=='approved';phase(r,'applying',action)
 f.phase(state,'worker_security_'+action+'_applying')
 result=json.loads(f.command('worker-security-'+action+'-apply',base.base.prefix()+['plugin','apply',r['operation_id']]+base.base.options(native),timeout=600))
 f.save(action+'-completed.json',result);assert result['state']=='completed' and result['traffic_resumed']
 phase(r,'completed_needs_verification',action);print(action+': completed; preservation verification next',flush=True)
def verify(action):
 state,native=context();r=f.load(path(action));assert r['state']=='completed_needs_verification'
 before=f.load(PRIVATE/(action+'-before.json'));after=base.snapshot(state,'worker-security-'+action+'-after');scope=r['scope']
 inst=next(x for x in before['mp_plugin_installation'] if x['public_id']==scope['installation_id']);workspace=next(x for x in before['mp_workspace'] if x['public_id']==scope['workspace_id'])
 bundle=f.load(OUT/(action+'-bundle.json'));stage=native.store.root/'stages'/r['operation_id'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
 observed=ReferenceDispatchMaintenance(native).inspect();assert observed==enabled['after']
 changed_jobs=0
 for table,rows in before.items():
  expected=copy.deepcopy(rows);actual=after[table];assert len(expected)==len(actual)
  if table=='mp_plugin_installation' and action=='upgrade':
   row=next(x for x in expected if x['id']==inst['id']);current=next(x for x in actual if x['id']==row['id'])
   assert {k for k in row if row[k]!=current[k]}=={'version','artifact_digest','manifest'}
   metadata=f.load(PRIVATE/'metadata.json');assert current['version']==metadata['version'] and current['artifact_digest']==metadata['digest']
   row.update(**{k:current[k] for k in ['version','artifact_digest','manifest']})
  elif table=='mp_workspace_plugin':
   row=next(x for x in expected if x['installation_id']==inst['id'] and x['workspace_id']==workspace['id']);current=next(x for x in actual if x['id']==row['id'])
   assert row['availability']==('enabled' if action=='suspend' else 'suspended') and current['availability']==('enabled' if action=='enable' else 'suspended')
   row.update(availability=current['availability'],write_date=current['write_date'])
  elif table=='mp_workspace':next(x for x in expected if x['id']==workspace['id'])['policy_generation']+=1
  elif table=='mp_job':
   byid={x['id']:x for x in actual}
   for row in expected:
    current=byid[row['id']];changed={k for k in row if row[k]!=current[k]};assert changed<={'release_digest','claim_generation','dispatch_generation'}
    if changed:
     assert current['release_digest']==bundle['plan']['target_release_digest'] and current['claim_generation']==row['claim_generation']+1 and current['dispatch_generation']==ready['control']['generation']
     row.update(**{k:current[k] for k in changed});changed_jobs+=1
  assert expected==actual,table+' outside scoped metadata/feature/policy/epoch footprint'
 assert base.schema(state,'worker-security-'+action+'-schema-after')==f.load(PRIVATE/(action+'-schema-before.json'))['digest']
 assert json.loads(f.sql(state,'worker-security-'+action+'-modules-after','BEGIN READ ONLY;SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m;ROLLBACK;'))==f.load(PRIVATE/(action+'-modules-before.json'))
 assert base.worker(native,'worker-security-'+action+'-worker-after')==f.load(PRIVATE/(action+'-worker-before.json'))
 files=json.loads(f.command('worker-security-'+action+'-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
 retained={};prefix='filestore/'+state['active_db']+'/'
 with tarfile.open(native.store.root/'checkpoints'/r['operation_id']/'filestore.tar.gz','r:gz') as archive:
  for member in archive:
   if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
 assert len(retained)==50 and all(files.get(p)==h for p,h in retained.items())
 assert native.config['generation']==(31 if action in ('upgrade','enable') else 30)
 f.save(action+'-preservation.json',dict(result='passed_actual_reviewed_'+action,operation_id=r['operation_id'],configuration_generation=native.config['generation'],dispatch_generation=observed['control']['generation'],tables=17,old_jobs_exact_except_epochs=37,changed_job_epochs=changed_jobs,original_notes=30,files_retained=len(retained),native_schema_modules_exact=True,independent_worker_exact=True))
 phase(r,'verified',action);f.phase(state,'worker_security_'+action+'_verified');print(action+': all17tables/schema/modules/50files/worker preserved under exact lifecycle footprint',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['suspend','upgrade','enable']);p.add_argument('step',choices=['prepare','approve','apply','verify']);a=p.parse_args();globals()[a.step](a.action)
