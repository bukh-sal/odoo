"""Read-only repository-owned Docker inventory; never select by prefix alone."""
import json,re,subprocess,sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-docker-retention'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
assert not LOCAL.exists();protect_directory(LOCAL)
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=45)
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
sources=set((ROOT/'.local').glob('*/state.json'))|set((ROOT/'.local').glob('*/operator/target.json'))|set((ROOT/'.local').glob('*/operator/worker-target.json'))|set((ROOT/'.local/operator/targets').glob('*.json'))
sources|=set((ROOT/'.local/r0').glob('*.json'))
projects=defaultdict(list);images=defaultdict(list)
def collect(value,source,trail=''):
 if isinstance(value,dict):
  for key,item in value.items():
   where=trail+'/'+key
   if key in {'project','project_name','compose_project','service_project'} and isinstance(item,str) and re.fullmatch(r'mp-[a-zA-Z0-9_-]+',item):projects[item].append(dict(source=source,key=where))
   if 'image' in key and isinstance(item,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',item):images[item].append(dict(source=source,key=where))
   collect(item,source,where)
 elif isinstance(value,list):
  for index,item in enumerate(value):collect(item,source,trail+'/'+str(index))
for path in sorted(sources):
 assert path.resolve().is_relative_to(ROOT/'.local') and not path.is_symlink()
 collect(load(path),path.relative_to(ROOT).as_posix())
for path in sorted((ROOT/'docs/evidence').glob('**/candidate-build.json')):
 value=load(path)
 if value.get('state')=='built' and value.get('git_base'):
  result=subprocess.run(['git','cat-file','-t',value['git_base']],cwd=ROOT,capture_output=True,timeout=10)
  if result.returncode==0 and result.stdout.strip()==b'commit':collect(value,path.relative_to(ROOT).as_posix())
current=load(ROOT/'.local/g6-events/operator/target.json');state=load(ROOT/'.local/g6-events/state.json')
assert current['generation']==27 and current['image_id']==state['image_id']
lines=call(['docker','ps','--all','--no-trunc','--format','{{json .}}']).decode().splitlines();listed=[json.loads(line) for line in lines]
save(LOCAL/'all-container-list.json',listed)
def label_map(value):return dict(item.split('=',1) for item in value.get('Labels','').split(',') if '=' in item)
owned_ids=[];unmatched=[]
for item in listed:
 labels=label_map(item);project=labels.get('com.docker.compose.project') or labels.get('com.modular.disposable')
 if project in projects:owned_ids.append(item['ID'])
 elif labels.get('com.modular.deployment')==current['deployment_id'] and item['Names'].startswith(state['project']+'-op-'):owned_ids.append(item['ID'])
 else:unmatched.append(dict(id=item['ID'],name=item['Names'],state=item['State'],reason='No exact project/deployment label bound to discovered repository state; preserve pending separate evidence.'))
infos=json.loads(call(['docker','inspect',*owned_ids])) if owned_ids else []
save(LOCAL/'owned-container-inspections.json',infos)
by_project=defaultdict(list);volume_users=defaultdict(list)
for info in infos:
 labels=info['Config']['Labels'] or {};project=labels.get('com.docker.compose.project') or labels.get('com.modular.disposable') or state['project']
 mounts=[dict(type=m['Type'],name=m.get('Name'),destination=m['Destination'],rw=m['RW']) for m in info['Mounts']]
 by_project[project].append(dict(id=info['Id'],name=info['Name'][1:],state=info['State']['Status'],exit_code=info['State']['ExitCode'],image=info['Image'],mounts=mounts))
 for mount in info['Mounts']:
  if mount['Type']=='volume':volume_users[mount['Name']].append(info['Id'])
volume_list=[json.loads(line) for line in call(['docker','volume','ls','--format','{{json .}}']).decode().splitlines()]
save(LOCAL/'all-volume-list.json',volume_list)
volume_ids=[v['Name'] for v in volume_list if label_map(v).get('com.docker.compose.project') in projects or v['Name'] in volume_users]
volumes=json.loads(call(['docker','volume','inspect',*volume_ids])) if volume_ids else []
save(LOCAL/'owned-volume-inspections.json',volumes)
image_list=[json.loads(line) for line in call(['docker','image','ls','--all','--no-trunc','--format','{{json .}}']).decode().splitlines()]
present=sorted({v['ID'] for v in image_list}&images.keys());image_info=json.loads(call(['docker','image','inspect',*present])) if present else []
save(LOCAL/'owned-image-inspections.json',image_info)
stage=ROOT/'.local/g6-events/operator/control/stages'/load(ROOT/'.local/g6-events/canvas4-upgrade-01.json')['operation_id']
checkpoint_image=load(stage/'configuration.json')['image_id']
protected=dict(current_project=state['project'],current_image=current['image_id'],current_app=current['worker_id'],current_checkpoint_image=checkpoint_image,known_hung_container='f84615e578404770c795cb92949d2e232c3a30f8cfd683debf3b3cbb29907213',browser_profiles='Prior deletion automatically rejected; no deletion or alternate attempt permitted here.',rules=['No global prune, force removal, daemon restart, or unknown data reset.','Never delete unrelated Arcadia assets.','Preserve current app, edge, PostgreSQL, external worker, named runtime volumes, independently approved authority and latest actual checkpoint.','Initial inventory is read-only. Assess all mount users and explicit recovery roles before a retirement selection.'])
save(LOCAL/'ownership.json',dict(projects=projects,images=images,protected=protected))
save(LOCAL/'unmatched-containers.json',unmatched)
save(LOCAL/'project-inventory.json',dict(by_project))
summary=dict(result='read_only_repository_bound_Docker_ownership_inventory',utc=datetime.now(timezone.utc).isoformat(),repository_projects=len(projects),owned_containers=len(infos),owned_running=sum(i['State']['Running'] for i in infos),owned_stopped=sum(i['State']['Status']=='exited' for i in infos),preserved_unmatched_containers=len(unmatched),owned_volumes=len(volumes),present_repository_recorded_images=len(image_info),project_counts={p:dict(total=len(rows),states=dict(Counter(r['state'] for r in rows))) for p,rows in by_project.items()},current_image=current['image_id'],current_checkpoint_image=checkpoint_image,mutations=0,limits='Ownership audit only; no retirement or recovery-role assumption from names alone. Raw mounts/config/log-sensitive inventory remains protected outside Git.')
save(OUT/'audit.json',summary);save(LOCAL/'state.json',dict(state='ownership_audited',audit='docs/evidence/G7/20261102-docker-retention-01/audit.json'))
print(json.dumps(summary))
