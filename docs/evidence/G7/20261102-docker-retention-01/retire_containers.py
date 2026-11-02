"""Archive/remove only exited containers bound to repository state labels.

No volume, image, live process, unmatched asset or user data deletion.
"""
import gzip,importlib.util,json,subprocess,sys
from collections import Counter
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-docker-retention'
sp=importlib.util.spec_from_file_location('retention_current',OUT.parent/'20261102-canvas4-source-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.operator_os import protect_directory
f=m.f;f.OUTPUT=OUT
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=45)
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
assert load(LOCAL/'state.json')['state']=='ownership_audited'
ownership=load(LOCAL/'ownership.json');known=load(LOCAL/'owned-container-inspections.json')
selected={v['Id']:v for v in known if v['State']['Status']=='exited' and not v['State']['Running']}
assert len(selected)==105 and ownership['protected']['known_hung_container'] not in selected
assert all(v['Name'][1:] not in {x['name'] for x in load(LOCAL/'unmatched-containers.json')} for v in selected.values())
current_ids={v['Id'] for v in known if v['State']['Running']};assert len(current_ids)==4 and not current_ids&selected.keys()
projects=ownership['projects']
for info in selected.values():
 labels=info['Config']['Labels'] or {};project=labels.get('com.docker.compose.project') or labels.get('com.modular.disposable')
 assert project in projects,'Exact repository project label proof required'
fresh=json.loads(call(['docker','inspect',*selected]))
assert len(fresh)==len(selected) and all(v['State']['Status']=='exited' and not v['State']['Running'] and v['Image']==selected[v['Id']]['Image'] and v['Name']==selected[v['Id']]['Name'] for v in fresh)
state,native=m.context();assert native.config['generation']==27
before=m.snapshot(state,'retention-containers-current-before');worker=m.worker(native,'retention-containers-worker-before')
volumes_before=sorted(call(['docker','volume','ls','--format','{{.Name}}']).decode().split())
archive=protect_directory(LOCAL/'container-archives');marker=LOCAL/'container-retirement.json';assert not marker.exists()
record=dict(state='archiving',selected=list(selected),archived=[],removed=[],preserve_volumes=True);save(marker,record)
for ident,info in selected.items():
 path=archive/(ident+'.inspect.json.gz');assert not path.exists()
 with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
 if info['HostConfig']['LogConfig']['Type']!='none':
  logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=45)
  assert logs.returncode==0,'Inspect original log-read failure; do not retire without diagnostics'
  with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
 record['archived'].append(ident);save(marker,record)
record['state']='deleting_exact_exited_containers';save(marker,record)
for index,ident in enumerate(selected):
 info=json.loads(call(['docker','inspect',ident]))[0]
 assert info['State']['Status']=='exited' and not info['State']['Running'] and info['Image']==selected[ident]['Image'] and info['Name']==selected[ident]['Name']
 record['pending']=ident;save(marker,record)
 call(['docker','rm',ident])  # deliberately no force and no volume flag
 record['removed'].append(ident);record.pop('pending');save(marker,record)
 if (index+1)%25==0:print(json.dumps(dict(retired=index+1,total=len(selected))),flush=True)
remaining=set(call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split())
assert not selected.keys()&remaining and current_ids<=remaining
assert sorted(call(['docker','volume','ls','--format','{{.Name}}']).decode().split())==volumes_before
assert m.snapshot(state,'retention-containers-current-after')==before and m.worker(native,'retention-containers-worker-after')==worker
record['state']='terminal_containers_retired_volumes_preserved';save(marker,record)
save(LOCAL/'state.json',dict(state='terminal_containers_retired_volume_retention_pending',container_marker=str(marker.relative_to(ROOT))))
counts=Counter((v['Config']['Labels'] or {}).get('com.docker.compose.project') or (v['Config']['Labels'] or {}).get('com.modular.disposable') for v in selected.values())
f.save('container-retirement.json',dict(result='retired_exact_105_exited_repository_owned_containers',removed_containers=len(selected),by_project=dict(counts),all_diagnostics_archived_privately=True,
 volumes_removed=0,all_prior_volume_names_preserved=True,images_removed=0,current4owned_runtime_containers_17tables_36jobs_30Notes_board_worker_exact=True,unmatched_or_unrelated_assets_touched=0,no_force_no_global_prune=True,
 remaining_work='Assess cold archives/recovery roles for now-unused known fixture volumes and exact unused recorded images. Do not reset unknown data or delete current/checkpoint resources. Historical configurations remain as evidence, not instructions to resume completed operations.'))
print('105 exact exited repository-owned containers archived/removed; every volume, current data/worker and all unmatched assets preserved')
