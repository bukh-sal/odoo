"""Complete private recovery inputs and ordinary independently reviewed CLI steps."""
import argparse,configparser,hashlib,json,shutil,sqlite3,sys
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
from clean_recovery_fixture import ROOT,LOCAL,OUTPUT,load,write,save,phase,guard,command
from modular_platform.catalog import Catalog
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import protect_directory
from modular_platform.deployment import inspect_image
from modular import configuration


def context():
 state=load(LOCAL/'state.json');guard(state);record=load(LOCAL/'fault-operation.json');assert record['state']=='recovery_required_native_committed';return state,record

def kit(resume=False):
 state,record=context();assert state['phase']==('capturing_complete_recovery_inputs' if resume else 'native_fault_requires_recovery');assert (LOCAL/'recovery-kit').exists()==resume;root=protect_directory(LOCAL/'recovery-kit');operation=record['operation_id'];checkpoint=LOCAL/'operator/control/checkpoints'/operation;manifest=load(checkpoint/'manifest.json');assert manifest['operation_id']==operation and manifest['plan_hash']==record['plan_hash'];phase(state,'capturing_complete_recovery_inputs')
 target=LOCAL/'operator/target.json';validator=configuration(LOCAL/'operator/trust.json');secret=protect_directory(root/'separately-secured-secrets')
 if resume:
  original=(LOCAL/'logs/capture-private-runtime-config.stdout').resolve();destination=(secret/'odoo_config').resolve();assert original.is_relative_to(LOCAL.resolve()) and destination.is_relative_to(LOCAL.resolve()) and not destination.exists()
  original.rename(destination);raw=destination.read_bytes();save('recovery-kit-attempt.json',dict(result='fixture_line_ending_expectation',diagnosis='Host ConfigParser wrote CRLF; transfer read_text normalized LF. Actual volume bytes retained as the authoritative config; compare parsed values. Original private config capture moved intact out of diagnostic logs into the dedicated secret-recovery domain.',raw_config_preserved=True))
 else:
  executor=NativeExecutor(OperatorStore(LOCAL/'operator/control'),target,LOCAL/'operator/catalog',validator);args,name=executor._child(operation,'kit-config',network=False)
  import subprocess
  captured=subprocess.run(args+['-c',"from pathlib import Path;import sys;sys.stdout.buffer.write(Path('/run/secrets/odoo_config').read_bytes())"],capture_output=True,timeout=30);assert captured.returncode==0;raw=captured.stdout;(secret/'odoo_config').write_bytes(raw)
 actual=configparser.ConfigParser();actual.read_string(raw.decode());expected=configparser.ConfigParser();expected.read(LOCAL/'odoo.conf');assert dict(actual['options'])==dict(expected['options'])

 for filename in ['postgres-password','app-db-password','bootstrap-password','database-master-password','alice-new-password','native-auth-password','native-auth-new-password','totp-old-secret','totp-new-secret']:shutil.copyfile(LOCAL/filename,secret/filename)
 cfg=configparser.ConfigParser();cfg.read_string(raw.decode());allowed={'db_host','db_port','db_user','db_name','dbfilter','list_db','data_dir','addons_path','server_wide_modules','without_demo','max_cron_threads','workers','db_maxconn','http_interface','proxy_mode','limit_memory_soft','limit_memory_hard','log_handler'};nonsecret={k:v for k,v in cfg['options'].items() if k in allowed};write(root/'nonsecret-runtime-configuration.json',nonsecret);write(root/'deployment-configuration.json',load(target));runtime=inspect_image(state['image_id']);write(root/'distribution-inventory.json',runtime['inventory']);write(root/'release-lock.json',manifest['previous_release']['release_lock'])
 cp=protect_directory(root/'coordinated-checkpoint')
 for file,digest in manifest['files'].items():assert hashlib.sha256((checkpoint/file).read_bytes()).hexdigest()==digest;shutil.copyfile(checkpoint/file,cp/file)
 shutil.copyfile(checkpoint/'manifest.json',cp/'manifest.json');shutil.copytree(LOCAL/'operator/catalog',root/'catalog',copy_function=shutil.copyfile);shutil.copyfile(LOCAL/'operator/trust.json',root/'trust.json');assert Catalog(root/'catalog',configuration(root/'trust.json'),readonly=True).snapshot()==Catalog(LOCAL/'operator/catalog',validator,readonly=True).snapshot()
 with closing(sqlite3.connect('file:'+str((LOCAL/'operator/control/control.sqlite3').resolve()).replace('\\','/')+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(root/'independent-control.sqlite3')) as target_db:source.backup(target_db)
 shutil.copyfile(LOCAL/'operator/control/policy.json',root/'independent-policy.json');source_dir=protect_directory(root/'host-operator-source')
 for folder in ['packages/platform_sdk','packages/contracts']:
  shutil.copytree(ROOT/folder,source_dir/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 (source_dir/'tools').mkdir();shutil.copyfile(ROOT/'tools/modular.py',source_dir/'tools/modular.py');(source_dir/'deploy').mkdir()
 for path in (ROOT/'deploy').iterdir():
  if path.suffix in ['.lock','.in'] or path.name=='runtime.lock.json':shutil.copyfile(path,source_dir/'deploy'/path.name)
 for filename in ['LICENSE','COPYRIGHT']:shutil.copyfile(ROOT/filename,source_dir/filename)
 (root/'SECRET-RECOVERY-INSTRUCTIONS.md').write_text('Private disposable rehearsal only. Restore requires the current failed DB and latest independently owned control/authority, not only the older checkpoint. Keep appconfig/dbconfig and current authority available. Secrets and native credential state must never enter public status/evidence. The separately-secured-secrets directory is owner-protected and never an application mount. Do not replay the old plan or replace current control with its historical snapshot. Select exact image/catalog/policy/configuration and obtain fresh restore/resume reviews.\n',encoding='utf8')
 command('retain-exact-runtime-image',['docker','image','save','--output',str(root/'runtime-image.tar'),state['image_id']],timeout=300)
 files={}
 for p in root.rglob('*'):
  if p.is_file():
   with p.open('rb') as stream:files[p.relative_to(root).as_posix()]=hashlib.file_digest(stream,'sha256').hexdigest()
 write(root/'kit-inventory.json',dict(schema_version=1,operation_id=operation,files=files));phase(state,'recovery_kit_verified');save('recovery-kit.json',dict(result='passed_complete_private_inputs',operation_id=operation,files=len(files),inventory_sha256=hashlib.sha256((root/'kit-inventory.json').read_bytes()).hexdigest(),database_and_filestore_hashes_verified=True,nonsecret_runtime_configuration=nonsecret,code_release_image_saved=True,dependency_and_artifact_locks=True,independent_control_snapshot_separate=True,secrets_separately_owner_protected=True,limits=['Inputs collected in the new clean rehearsal. Ordinary restore still uses the current failed DB for authoritative revocation reconciliation.','Historical control snapshot is backup evidence, never replayed or substituted for the current journal.','Image and private kit remain local; no publication or disaster/host-authority-loss claim.']));guard(state)

def step(action):
 state,record=context();mapping={'prepare-restore':('recovery_kit_verified','restore_reviewed','restore-decision.json'),'restore':('restore_reviewed','restored_verified_traffic_closed','restore-decision.json'),'prepare-resume':('restored_verified_traffic_closed','resume_reviewed','resume-decision.json'),'resume':('resume_reviewed','restored_resumed','resume-decision.json')};expected,finished,filename=mapping[action];assert state['phase']==expected;operation=record['operation_id'];prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(LOCAL/'operator/trust.json'),'plugin','recover',action,operation,'--store',str(LOCAL/'operator/control'),'--deployment-config',str(LOCAL/'operator/target.json'),'--catalog',str(LOCAL/'operator/catalog')]
 if action in ['restore','resume']:
  sealed=load(LOCAL/(filename+'.hash'));prefix+=['--decision',str(LOCAL/filename),'--decision-hash',sealed['decision_hash'],'--noninteractive']
 phase(state,'running_'+action);result=json.loads(command('runbook-'+action,prefix,timeout=600))
 if action.startswith('prepare-'):
  assert set(result)>={'decision','decision_hash'};private=result['decision'];assert private['action']==('restore_to_fresh_database' if action=='prepare-restore' else 'resume_verified_restore');# CLI expects the decision itself, not its surrounding CLI response envelope.
  decision_file=LOCAL/filename;write(LOCAL/(filename+'.envelope'),result);write(decision_file,private)
  write(LOCAL/(filename+'.hash'),dict(decision_hash=result['decision_hash']))
  # Reconstitute only a safe short observation for public evidence.
  public=dict(result='review_prepared',action=action,operation_id=operation,decision_hash=result['decision_hash'],review=private['review'],keep_traffic_closed=True,native_auth_bound=(private.get('authority',{}).get('native_auth_policy')=='r1-current-native-auth-v1' if action=='prepare-restore' else bool(private.get('authority_digest'))));save('runbook-'+action+'.json',public)
 else:
  assert result['state']==('restored_verified' if action=='restore' else 'restored_traffic_resumed');save('runbook-'+action+'.json',result)
  target=load(LOCAL/'operator/target.json');state.update(active_db=target['sites'][0]['database'],image_id=target['image_id']);state['databases']=sorted(set(state['databases']+[state['active_db']]))
 phase(state,finished);guard(state);print(json.dumps(dict(result=finished,operation_id=operation)))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['kit','resume-kit-config','prepare-restore','restore','prepare-resume','resume']);args=parser.parse_args()
 if args.action in ['kit','resume-kit-config']:kit(args.action=='resume-kit-config')
 else:step(args.action)
