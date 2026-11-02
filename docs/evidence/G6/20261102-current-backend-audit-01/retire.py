"""Retire this audit's exact exited native and receipt-bound observer children."""
import gzip,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import audit as d
from modular_platform.operator_os import protect_directory
def call(args):return subprocess.check_output(args,cwd=d.ROOT,timeout=30)
state,native=d.current.context();assert d.f.load(d.MARKER)['state']=='backend_coverage_verified'
assert not (d.OUT/'retirement.json').exists()
selected={}
for suffix,expected in [('01',1),('02',0)]:
    name=state['project']+'-current-backend-native-guards-'+suffix
    info=json.loads(call(['docker','inspect',name]))[0]
    assert info['Name']=='/'+name and info['Image']==native.config['image_id']
    assert info['Config']['Labels']['com.modular.disposable']==state['project']
    assert info['State']['Status']=='exited' and not info['State']['Running'] and info['State']['ExitCode']==expected
    assert info['HostConfig']['LogConfig']['Type']=='none';selected[info['Id']]=info
observations=0
for line in call(['docker','ps','--all','--no-trunc','--filter','label=com.modular.deployment='+native.config['deployment_id'],'--filter','status=exited','--format','{{.ID}} {{.Names}}']).decode().splitlines():
    ident,name=line.split();prefix=state['project']+'-op-';suffix='-dispatch-observe'
    if not name.startswith(prefix) or not name.endswith(suffix):continue
    operation=name[len(prefix):-len(suffix)];receipt=native.store.root/'dispatch-inspections'/operation/'observe.json'
    if not receipt.is_file():continue
    info=json.loads(call(['docker','inspect',ident]))[0]
    if info['Image']!=native.config['image_id']:continue
    labels=info['Config']['Labels'];value=d.f.load(receipt)
    assert labels['com.modular.operation']==operation and labels['com.modular.deployment']==native.config['deployment_id']
    assert value['child']==name and value['action']=='observe'
    assert not info['State']['Running'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
    assert info['HostConfig']['LogConfig']['Type']=='none'
    selected[ident]=info;observations+=1
worker=d.base.worker(native,'current-backend-retire-worker-before')
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
assert not {current,worker['container_id']}&selected.keys()
archive=protect_directory(d.ROOT/'.local/retired-docker-20261102/current-backend-audit')
for ident,info in selected.items():
    path=archive/(ident+'.json.gz');assert not path.exists()
    with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
    call(['docker','rm',ident])
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
assert not selected.keys()&remaining and {current,worker['container_id']}<=remaining
assert d.base.snapshot(state,'current-backend-retire-data-after')==d.f.load(d.PRIVATE/'data-before.json')
assert d.base.worker(native,'current-backend-retire-worker-after')==worker
d.f.save('retirement.json',dict(result='retired_exact_current_backend_audit_children',removed_containers=len(selected),
    native_guard_children=2,receipt_bound_readonly_observers=observations,expected_failed_fixture_exit1_archived=True,
    raw_private_logs_retained=True,all17tables_worker_current_app_and_checkpoint_roles_preserved=True,
    new_images=0,volumes_created_or_removed=0,no_global_prune=True))
d.f.write(d.MARKER,dict(d.f.load(d.MARKER),state='backend_audit_complete_cleaned'))
d.f.guard(state);print('Retired '+str(len(selected))+' exact owned terminal children; current backend audit complete, browser still pending')
