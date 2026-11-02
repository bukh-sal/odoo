"""Verify retained notices and retire only the two completed no-mount collectors."""
import gzip,hashlib,importlib.util,json,os,subprocess,zipfile
from pathlib import Path,PurePosixPath
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-current-provenance-01'
sp=importlib.util.spec_from_file_location('retire_provenance_collectors',OUT.parent/'20261102-notes8-labels4-read-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context();assert native.config['generation']==29
index=f.load(OUT/'notice-bundle-final.json');archive=LOCAL/'release-notices-final.zip'
with archive.open('rb+') as stream:os.fsync(stream.fileno());assert hashlib.file_digest(stream,'sha256').hexdigest()==index['archive_sha256']
with zipfile.ZipFile(archive) as z:
 assert len(z.namelist())==len(set(z.namelist()))==len(index['files'])==411
 assert not any(PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts for name in z.namelist())
 for row in index['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
names={f.load(LOCAL/'intent.json')['container']:state['image_id'],f.load(LOCAL/'worker-intent.json')['container']:f.load(OUT/'worker-provenance.json')['image_id']}
infos=json.loads(subprocess.check_output(['docker','inspect',*names],timeout=30));assert len(infos)==2
for info in infos:
 assert names[info['Name'].removeprefix('/')]==info['Image'] and info['State']['Status']=='exited' and info['State']['ExitCode']==0
 assert info['Config']['Labels']['com.modular.disposable']==state['project'] and info['HostConfig']['NetworkMode']=='none' and info['Mounts']==[]
 with gzip.open(LOCAL/(info['Id']+'.collector.json.gz'),'wb') as stream:stream.write(json.dumps(info).encode())
 subprocess.check_output(['docker','rm',info['Id']],timeout=30)
assert m.snapshot(state,'g7-provenance-retire-source-after')==f.load(LOCAL/'source-data-before.json') and m.worker(native,'g7-provenance-retire-worker-after')==f.load(LOCAL/'source-worker-before.json')
f.save('collector-retirement.json',dict(result='retired_two_exact_completed_offline_no_mount_collectors',removed_containers=2,notice_bundle_verified_files=411,notice_bundle_sha256=index['archive_sha256'],notice_bundle_fsynced=True,private_diagnostics_retained=True,current_image_worker_benchmark_original_data_volumes_preserved=True,no_global_prune=True,limits=['Static provenance subtask only; security/advisory/layer/history/network and fresh release qualification remain.']))
print(json.dumps(dict(removed_collectors=2,verified_notice_files=411,original_runtime_unchanged=True)))
