"""Retire verified operation children, exact test fixtures and receipt observers."""
import gzip,importlib.util,json,subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('retire_notes8',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT
from modular_platform.operator_os import protect_directory
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
state,native=m.context();record=f.load(m.MARKER);assert record['state']=='preservation_verified'
op=record['operation_id'];assert native.store.status(op)['state']=='completed'
base=f.load(native.store.root/'stages'/op/'configuration.json');oldapp=base['worker_id']
before=m.snapshot(state,'g7-notes8-retire-data-before');worker=m.worker(native,'g7-notes8-retire-worker-before')
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
first=f.load(OUT.parent/'20261102-notes8-labels4-candidate-01/candidate-build.json')['image_id']
expected={
 'g7-notes8-policy-candidate-01':(first,0),
 'g7-notes8-live-policy-candidate-01':(base['image_id'],0),
 'g7-notes8-fixed-policy-candidate-01':(state['image_id'],0),
 'g7-read-notes8-candidate-readonly-native-01':(state['image_id'],0),
 'g7-notes8-profile-01':(state['image_id'],0),
 'notes8-labels4-extract':(state['image_id'],0),
 'g7-read-notes8-installed-native-01':(state['image_id'],0),
 'g7-notes8-canvas-paths-02':(state['image_id'],0)}
names={state['project']+'-'+suffix:value for suffix,value in expected.items()}
ids=call(['docker','ps','--all','--no-trunc','--filter','name='+state['project'],'--format','{{.ID}}']).decode().split()
selected={};counts=dict(native_tests=0,operation_children=0,observers=0,superseded_apps=0)
for info in json.loads(call(['docker','inspect',*ids])):
 name=info['Name'][1:];labels=info['Config']['Labels'] or {};kind=None
 if name in names:
  image,exitcode=names[name];assert info['Image']==image and info['State']['ExitCode']==exitcode
  assert labels['com.modular.disposable']==state['project'];kind='native_tests'
 elif info['Id']==oldapp:
  assert labels['com.docker.compose.project']==state['project'] and labels['com.docker.compose.service']=='app' and info['Image']==base['image_id'];kind='superseded_apps'
 elif labels.get('com.modular.operation')==op and labels.get('com.modular.deployment')==native.config['deployment_id']:
  assert info['Image'] in (base['image_id'],native.config['image_id']) and info['State']['ExitCode']==0;kind='operation_children'
 elif name.startswith(state['project']+'-op-') and name.endswith('-dispatch-observe'):
  observation=name[len(state['project']+'-op-'):-len('-dispatch-observe')]
  receipt=native.store.root/'dispatch-inspections'/observation/'observe.json'
  if not receipt.is_file():continue
  value=f.load(receipt)
  assert labels['com.modular.operation']==observation and labels['com.modular.deployment']==native.config['deployment_id']
  assert value['child']==name and value['action']=='observe' and info['State']['ExitCode']==0;kind='observers'
 if kind:
  assert not info['State']['Running'] and info['State']['Status']=='exited' and info['Id'] not in (current,worker['container_id'])
  selected[info['Id']]=info;counts[kind]+=1
assert counts['native_tests']==len(expected) and counts['superseded_apps']==1
archive=protect_directory(ROOT/'.local/retired-docker-20261102/g7-notes8-labels4')
for ident,info in selected.items():
 path=archive/(ident+'.json.gz');assert not path.exists()
 with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
 if info['HostConfig']['LogConfig']['Type']!='none':
  logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
  with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
 call(['docker','rm',ident])
assert m.snapshot(state,'g7-notes8-retire-data-after')==before and m.worker(native,'g7-notes8-retire-worker-after')==worker
f.save('retirement.json',dict(result='retired_exact_owned_terminal_helpers',counts=counts,removed_containers=len(selected),all17tables_current_worker_app_checkpoint_images_volumes_preserved=True,private_diagnostics_archived=True,no_global_prune=True))
builds=[f.load(OUT.parent/('20261102-notes8-labels4-candidate-'+number)/'candidate-build.json') for number in ['01','02','03','04']]
assert builds[3]['source_image_id']==builds[2]['image_id'] and builds[3]['image_id']==native.config['image_id'] and builds[3]['base_image_id']==base['image_id']
removed=[]
for tag,ident in zip(builds[3]['aliases'],[builds[3]['base_image_id'],builds[3]['source_image_id']]):
 assert json.loads(call(['docker','image','inspect',tag]))[0]['Id']==ident
 call(['docker','image','rm','--no-prune',tag]);removed.append(tag)
for build in builds[:3]:
 ident=build['image_id'];info=json.loads(call(['docker','image','inspect',ident]))[0]
 assert not call(['docker','ps','--all','--filter','ancestor='+ident,'--format','{{.ID}}']).strip()
 assert info['RepoTags']==[build['tag']] and info['RepoDigests']==['modular-platform@'+ident]
 with gzip.open(archive/(ident[7:]+'.image.json.gz'),'wb') as stream:stream.write(json.dumps(info).encode())
 call(['docker','image','rm','--no-prune',build['tag']]);removed.append(build['tag'])
 assert ident not in set(call(['docker','image','ls','--all','--no-trunc','--format','{{.ID}}']).decode().split())
for image in [base['image_id'],state['image_id']]:assert json.loads(call(['docker','image','inspect',image]))[0]['Id']==image
f.save('compiler-retirement.json',dict(result='retired_exact_unused_compilers_wrong_policy_candidates_and_temporary_aliases',removed_tags=removed,removed_images=3,current_and_checkpoint_retained=True,no_global_prune=True))
print(json.dumps(dict(removed_containers=len(selected),counts=counts,removed_images=3,removed_tags=len(removed))))
