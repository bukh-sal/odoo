"""Exact completed operation helpers and replaced app; no shared resources."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT));import activate as m
f=m.f;f.OUTPUT=OUT;state,native=m.context('connector');record=f.load(m.PRIVATE/'state.json')
assert record['state']=='backend_qualified_native_uninstall_pending'
operation=record['operation_id'];assert native.store.status(operation)['state']=='completed'
old=f.load(native.store.root/'checkpoints'/operation/'manifest.json')['configuration']
ids=subprocess.check_output(['docker','ps','-aq','--filter','label=com.modular.operation='+operation]).decode().split()
assert len(ids)==7
ids.append(old['worker_id']);assert len(set(ids))==8 and native.config['worker_id'] not in ids
archive=m.PRIVATE/'retired-helpers';assert not archive.exists();archive.mkdir()
removed=[]
for ident in ids:
    info=json.loads(subprocess.check_output(['docker','inspect',ident]))[0]
    assert info['State']['Status']=='exited' and info['State']['ExitCode']==0
    if ident==old['worker_id']:
        assert info['Image']==old['image_id'] and info['Config']['Labels']['com.docker.compose.project']==state['project']
    else:
        assert info['Config']['Labels']['com.modular.operation']==operation
        assert info['Config']['Labels']['com.modular.deployment']==native.config['deployment_id']
        assert info['Name'].startswith('/'+state['project']+'-op-'+operation+'-')
    (archive/(info['Id']+'.json')).write_text(json.dumps(info,indent=2)+'\n')
    logs=subprocess.run(['docker','logs',info['Id']],capture_output=True,timeout=30)
    (archive/(info['Id']+'.stdout')).write_bytes(logs.stdout);(archive/(info['Id']+'.stderr')).write_bytes(logs.stderr)
    subprocess.run(['docker','rm',info['Id']],capture_output=True,check=True,timeout=30)
    removed.append(dict(id=info['Id'],name=info['Name'],exit_code=0))
f.guard(state)
f.save('retirement.json',dict(result='passed_exact_completed_operation_cleanup',retired=removed,
    containers_removed=len(removed),images_volumes_networks_removed=0,current_app_retained=native.config['worker_id'],
    worker_issuer_checkpoints_and_prior_images_retained=True,private_diagnostics_archived=True))
print(json.dumps(dict(result='completed_operation_helpers_retired',containers_removed=len(removed))))
