"""Archive and retire only this completed core22 operation's terminal containers."""
import json, subprocess, sys
from pathlib import Path
ROOT=Path.cwd(); OUT=Path(__file__).parent; sys.path.insert(0,str(OUT))
import activate as m
f=m.f; f.OUTPUT=OUT
state,native=m.context('connector'); record=f.load(m.PRIVATE/'state.json')
assert record['state']=='preservation_verified' and native.config['generation']==5
assert f.load(OUT/'completed.json')['state']=='completed'
assert f.load(m.PRIVATE/'http-state.json')['state']=='deleted_verified'
assert f.load(OUT/'http.json')['temporary_record_removed']
operation=record['operation_id']; project=state['project']
ids=subprocess.check_output(['docker','ps','-aq','--filter','name='+project+'-op-'+operation+'-']).decode().split()
old='927eb23eee7d'
info=json.loads(subprocess.check_output(['docker','inspect',*ids,old]))
assert len(ids)==7 and len(info)==8
archive=m.PRIVATE/'retired-containers'; archive.mkdir(exist_ok=False)
retired=[]
for item in info:
 name=item['Name'].lstrip('/'); labels=item['Config']['Labels']
 assert item['State']['Status']=='exited' and item['State']['ExitCode']==0
 assert item['Id']!=native.config['worker_id']
 if item['Id'].startswith(old):
  assert name==project+'-app-release-119ed496aa1142888e13b15ebd53280c'
  assert labels['com.docker.compose.project']==project
 else:
  assert name.startswith(project+'-op-'+operation+'-')
  assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id']
 (archive/(item['Id']+'.json')).write_text(json.dumps(item,indent=2)+'\n')
 logs=subprocess.run(['docker','logs',item['Id']],capture_output=True,timeout=30)
 (archive/(item['Id']+'.stdout')).write_bytes(logs.stdout)
 (archive/(item['Id']+'.stderr')).write_bytes(logs.stderr)
 subprocess.run(['docker','rm',item['Id']],check=True,capture_output=True,timeout=30)
 absent=subprocess.run(['docker','inspect','--type','container',item['Id']],capture_output=True,timeout=30)
 assert absent.returncode and b'no such' in absent.stderr.lower()
 retired.append(dict(id=item['Id'],name=name,exit_code=0,removed=True))
f.guard(state)
f.save('retirement.json',dict(result='passed_exact_completed_operation_cleanup',retired=retired,containers_removed=len(retired),images_volumes_networks_removed=0,current_app_retained=native.config['worker_id'],worker_issuer_checkpoints_retained=True,private_diagnostics_archived=True))
f.save('qualification.json',dict(result='passed_bounded_core22_native_XML_maintenance',image_id=record['image_id'],inventory_digest=record['inventory_digest'],configuration_generation=5,dispatch_generation=15,platform_version='0.1.22',native_core='19.0.0.1.22',evidence=['../20261104-defused-staging-01/static-resolution.json','../20261104-core22-defused-image-01/candidate-admission.json','completed.json','preservation.json','native-import.json','http.json','retirement.json'],checks=dict(immutable_native_and_parser=12,installed_native_import=3,HTTP=4),preservation=dict(tables=17,old_files=38,completed_job_epoch_updates=1,temporary_CRUD_record_removed=True,expected_owned_outbox_events=2),limits=['No full Expat/native CVE, API05 concurrency/crash, second same-target fresh build, fresh install/restore, accessibility or full release qualification claim.','Original demo and benchmark remain on their earlier immutable targets.']))
record['state']='backend_qualified'; f.write(m.PRIVATE/'state.json',record); f.phase(state,'core22_backend_qualified')
print(json.dumps(dict(result='core22_backend_qualified',containers_retired=len(retired))))

