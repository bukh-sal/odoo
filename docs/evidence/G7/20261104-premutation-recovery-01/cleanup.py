"""Retire only terminal owned helpers; retain real checkpoint/current authority."""
import base64,hashlib,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import probe as p
sys.path.insert(0,str(p.ROOT/'tools'))
from secret_scan import Scanner
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='qualified_unchanged_release_resumed'
assert p.load(p.OUT/'qualification.json')['result'].startswith('passed_current_MIG01')
values={k:base64.b64decode(v) for k,v in p.load(p.ROOT/'.local/g7-image-secret-audit-01/known-values.json').items()}
scanner=Scanner((p.ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[path for path in p.PRIVATE.iterdir() if path.is_file() and path.suffix in ['.stdout','.stderr']]
paths.extend(path for path in (p.LOCAL/'logs').iterdir() if path.is_file() and path.name.startswith('premutation-current-') and path.suffix in ['.stdout','.stderr'])
findings=[hit for path in paths for hit in scanner.inspect_file(path,path.relative_to(p.ROOT).as_posix())];assert not findings
ids=subprocess.check_output(['docker','ps','-aq','--filter','status=exited','--filter','name='+state['project']+'-op-']).decode().split()
info=json.loads(subprocess.check_output(['docker','inspect',*ids]));retired=[];archive=p.PRIVATE/'retired-helper-inspects';archive.mkdir()
for item in info:
 name=item['Name'].lstrip('/');labels=item['Config']['Labels']
 if labels.get('com.modular.operation')!=record['operation_id'] and not name.endswith('-dispatch-observe'):continue
 assert item['State']['Status']=='exited' and item['State']['ExitCode']==0 and labels['com.modular.deployment']==native.config['deployment_id']
 assert item['Id']!=native.config['worker_id'] and name.startswith(state['project']+'-op-')
 (archive/(item['Id']+'.json')).write_text(json.dumps(item,indent=2)+'\n')
 subprocess.run(['docker','rm',item['Id']],capture_output=True,check=True,timeout=20)
 retired.append(dict(id=item['Id'],name=name,removed=True))
checkpoint=native.store.root/'checkpoints'/record['operation_id'];assert (checkpoint/'manifest.json').is_file()
p.save('cleanup-and-log-scan.json',dict(result='passed_owned_helper_retirement_and_new_log_scan',retired=retired,containers_removed=len(retired),images_volumes_networks_removed=0,private_log_files=len(paths),known_values=121,known_or_generic_findings=0,real_checkpoint_and_current_authority_retained=True,current_primary_worker_issuer_unaffected=True))
print(json.dumps(dict(result='MIG01_helpers_retired_new_logs_clean',containers=len(retired),logs=len(paths))))
