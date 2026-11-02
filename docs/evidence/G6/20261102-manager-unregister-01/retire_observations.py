"""Retire exact owned terminal read-only inspection helpers, preserving receipts."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,MARKER,context,f,worker
from modular_platform.operator_os import protect_directory

def call(args):return subprocess.check_output(args,timeout=30)

state,native=context();cycle=f.load(MARKER);assert cycle['unregister']['state']=='preservation_verified'
assert (OUT/'unregister-retirement.json').exists() and not (OUT/'observation-retirement.json').exists()
ids=call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],
    '--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines()
selected=[]
for line in ids:
    ident,name=line.split();prefix=state['project']+'-op-'
    if not name.startswith(prefix) or not name.endswith('-dispatch-observe'):continue
    op=name[len(prefix):-len('-dispatch-observe')]
    receipt=native.store.root/'dispatch-inspections'/op/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0];labels=info['Config']['Labels'] or {}
    assert labels['com.modular.deployment']==native.config['deployment_id'] and labels['com.modular.operation']==op
    assert not info['State']['Running'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
    if info['Image']!=native.config['image_id']:continue
    record=f.load(receipt);assert record['child']==name and record['action']=='observe'
    selected.append(info)
remote=worker(native,'manager-unregister01-worker-before-observation-retirement')
archive=protect_directory(ROOT/'.local/retired-docker-20261102/current15-readonly-observations')
for info in selected:
    path=archive/(info['Id']+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    # Fixed child uses log-driver none; original stdout/stderr/receipt remain private.
    assert info['HostConfig']['LogConfig']['Type']=='none'
    call(['docker','rm',info['Id']])
remaining=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
assert not {i['Id'] for i in selected}&set(remaining)
assert worker(native,'manager-unregister01-worker-after-observation-retirement')==remote
f.save('observation-retirement.json',dict(result='retired_owned_completed_current15_readonly_inspection_helpers',removed_containers=len(selected),
    exact_deployment_project_image_exit0_and_durable_readonly_receipt_required=True,private_diagnostics_and_receipts_retained=True,
    active_host_database_edge_external_worker_and_checkpoint_roles_preserved=True,images_removed=0,volumes_removed=0,no_global_prune=True))
f.guard(state);print('Retired '+str(len(selected))+' exact completed read-only inspection helpers; active/recovery roles preserved')
