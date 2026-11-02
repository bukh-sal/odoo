"""Retire verified operation children, exact test fixtures and receipt observers."""
import gzip,importlib.util,json,subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('retire_canvas4',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT
from modular_platform.operator_os import protect_directory
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
state,native=m.context();record=f.load(m.MARKER);assert record['state']=='preservation_verified'
op=record['operation_id'];assert native.store.status(op)['state']=='completed'
base=f.load(native.store.root/'stages'/op/'configuration.json');oldapp=base['worker_id']
before=m.snapshot(state,'g7-canvas4-retire-data-before');worker=m.worker(native,'g7-canvas4-retire-worker-before')
current=json.loads(call(['docker','inspect',native.observer._container('app')]))[0]['Id']
expected={'g7-canvas4-seed-01':(base['image_id'],0),'canvas4-extract':(state['image_id'],0),'g7-canvas4-native-01':(state['image_id'],0)}
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
archive=protect_directory(ROOT/'.local/retired-docker-20261102/g7-canvas4')
for ident,info in selected.items():
 path=archive/(ident+'.json.gz');assert not path.exists()
 with gzip.open(path,'wb') as stream:stream.write(json.dumps(info).encode())
 if info['HostConfig']['LogConfig']['Type']!='none':
  logs=subprocess.run(['docker','logs',ident],capture_output=True,timeout=30)
  with gzip.open(archive/(ident+'.logs.gz'),'wb') as stream:stream.write(logs.stdout+b'\n'+logs.stderr)
 call(['docker','rm',ident])
assert m.snapshot(state,'g7-canvas4-retire-data-after')==before and m.worker(native,'g7-canvas4-retire-worker-after')==worker
f.save('retirement.json',dict(result='retired_exact_owned_terminal_helpers',counts=counts,removed_containers=len(selected),all17tables_current_worker_app_checkpoint_images_volumes_preserved=True,private_diagnostics_archived=True,no_global_prune=True))
build=f.load(OUT.parent/'20261102-canvas4-candidate-01/candidate-build.json');derived=f.load(OUT.parent/'20261102-canvas4-candidate-02/candidate-build.json')
assert derived['source_image_id']==build['image_id'] and derived['base_OS_Python_exact'] and derived['image_id']==native.config['image_id']
assert not call(['docker','ps','--all','--filter','ancestor='+build['image_id'],'--format','{{.ID}}']).strip()
tags=[*derived['aliases'],build['tag']]
for tag,image in zip(tags,[derived['base_image_id'],build['image_id'],build['image_id']]):assert json.loads(call(['docker','image','inspect',tag]))[0]['Id']==image
for tag in tags:call(['docker','image','rm',tag])
for image in [derived['base_image_id'],derived['image_id']]:assert json.loads(call(['docker','image','inspect',image]))[0]['Id']==image
f.save('compiler-retirement.json',dict(result='retired_exact_unused_compiler_and_temporary_aliases',removed_tags=tags,compiler_image=build['image_id'],current_and_checkpoint_retained=True,no_global_prune=True))
print(json.dumps(dict(removed_containers=len(selected),counts=counts,removed_compiler_tags=len(tags))))
