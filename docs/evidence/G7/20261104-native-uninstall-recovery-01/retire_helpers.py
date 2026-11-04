"""Retire only exact terminal recovery helpers and replaced app; retain failed DB."""
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).parent));import probe as p
from modular_platform.operator_os import protect_directory

def call(args):return subprocess.check_output(args,timeout=30)
state,native=p.context();record=p.load(p.PRIVATE/'state.json');assert record['state']=='ordinary_job_verified'
operation=record['operation_id'];status=native.store.status(operation);assert status['state']=='revoked' and status['traffic_resumed']
current=native.config['worker_id'];remote=p.worker(native,'native-uninstall-retire-worker-before')
assert remote==p.load(p.PRIVATE/'worker-before.json')
old=record['configuration']['worker_id'];assert old!=current
ids=call(['docker','ps','-aq','--filter','label=com.modular.operation='+operation]).decode().split();assert len(ids)==9
selected={}
for info in json.loads(call(['docker','inspect',*ids,old])):
    assert info['Id'] not in {current,remote['id']} and info['State']['Status']=='exited' and info['State']['ExitCode']==0
    labels=info['Config']['Labels'] or {}
    if info['Id']==old:
        assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app'
    else:
        assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id']
        assert info['Name'].startswith('/'+state['project']+'-op-'+operation+'-')
    assert info['Image']==native.config['image_id'];selected[info['Id']]=info
assert old in selected
observations=0
lines=call(['docker','ps','-a','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],
    '--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines()
for line in lines:
    ident,name=line.split();prefix=state['project']+'-op-';suffix='-dispatch-observe'
    if ident in selected or not name.startswith(prefix) or not name.endswith(suffix):continue
    op=name[len(prefix):-len(suffix)];receipt=native.store.root/'dispatch-inspections'/op/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0]
    if info['Image']!=native.config['image_id']:continue
    value=p.load(receipt);labels=info['Config']['Labels'] or {}
    assert labels['com.modular.operation']==op and labels['com.modular.deployment']==native.config['deployment_id']
    assert value['child']==name and value['action']=='observe' and info['State']['Status']=='exited' and info['State']['ExitCode']==0
    selected[ident]=info;observations+=1
archive=protect_directory(p.PRIVATE/'retired-helpers');removed=[]
for ident,info in selected.items():
    (archive/(ident+'.json')).write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
    (archive/(ident+'.stdout')).write_bytes(logs.stdout);(archive/(ident+'.stderr')).write_bytes(logs.stderr)
    subprocess.run(['docker','rm',ident],capture_output=True,check=True,timeout=30)
    removed.append(dict(id=ident,name=info['Name'],exit_code=0))
assert p.snapshot(state,'native-uninstall-retire-data-final')==p.load(p.PRIVATE/'data-final.json')
assert p.worker(native,'native-uninstall-retire-worker-after')==remote
jobop=p.load(p.OUT/'ordinary-runner.json')['operation_id']
assert not call(['docker','ps','-aq','--filter','label=com.modular.job_operation='+jobop]).strip()
p.f.guard(state)
p.save('retirement.json',dict(result='passed_exact_terminal_recovery_helper_cleanup',retired=removed,
    containers_removed=len(removed),dispatch_observers_removed=observations,ordinary_job_helper_auto_removed=True,
    images_volumes_networks_removed=0,current_app_retained=current,worker_issuer_checkpoint_and_failed_database_retained=True,
    private_diagnostics_archived=True,all_final17tables_and_worker_exact=True))
print(json.dumps(dict(result='terminal_recovery_helpers_retired',containers_removed=len(removed))),flush=True)
