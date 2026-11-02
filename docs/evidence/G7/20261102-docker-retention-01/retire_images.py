"""Retire only unused recorded obsolete images, preserving protected roles."""
import gzip,importlib.util,json,subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-docker-retention'
sp=importlib.util.spec_from_file_location('image_retention_current',OUT.parent/'20261102-canvas4-source-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.operator_os import protect_directory
f=m.f;f.OUTPUT=OUT
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
assert load(LOCAL/'state.json')['state']=='cold_volumes_retired_image_retention_pending'
plan=load(LOCAL/'archive-plan.json');assert len(plan['images'])==28
state,native=m.context();assert native.config['generation']==27
before=m.snapshot(state,'retention-images-current-before');worker=m.worker(native,'retention-images-worker-before')
before_ids=set(call(['docker','image','ls','--all','--no-trunc','--format','{{.ID}}']).decode().split())
archive=protect_directory(LOCAL/'image-archives');marker=LOCAL/'image-retirement.json';assert not marker.exists()
record=dict(state='retiring_exact_unused_recorded_images',removed=[],removed_tags=[],protected=plan['protected_images']);save(marker,record)
for index,item in enumerate(plan['images']):
 ident=item['image'];assert ident not in plan['protected_images'] and ident in before_ids and item['source_records']
 assert not call(['docker','ps','--all','--filter','ancestor='+ident,'--format','{{.ID}}']).strip()
 info=json.loads(call(['docker','image','inspect',ident]))[0]
 assert info['Id']==ident and sorted(info.get('RepoTags') or [])==sorted(item['tags'])
 assert all(tag.startswith(('modular-platform:','modular-document-stats:')) for tag in item['tags'])
 with gzip.open(archive/(ident[7:]+'.inspect.json.gz'),'wb') as stream:stream.write(json.dumps(info).encode())
 record['pending_image']=ident;save(marker,record)
 if item['tags']:
  for tag in item['tags']:
   assert json.loads(call(['docker','image','inspect',tag]))[0]['Id']==ident
   call(['docker','image','rm','--no-prune',tag]);record['removed_tags'].append(tag);save(marker,record)
 else:call(['docker','image','rm','--no-prune',ident])
 present=set(call(['docker','image','ls','--all','--no-trunc','--format','{{.ID}}']).decode().split());assert ident not in present
 record['removed'].append(ident);record.pop('pending_image');save(marker,record)
 if (index+1)%5==0:print(json.dumps(dict(unused_recorded_images_retired=index+1,total=len(plan['images']))),flush=True)
after_ids=set(call(['docker','image','ls','--all','--no-trunc','--format','{{.ID}}']).decode().split());selected={v['image'] for v in plan['images']}
assert before_ids-selected==after_ids and not selected&after_ids
assert {v for v in plan['protected_images'] if v in before_ids}<=after_ids
assert m.snapshot(state,'retention-images-current-after')==before and m.worker(native,'retention-images-worker-after')==worker
record['state']='exact_28_obsolete_recorded_images_retired';save(marker,record)
save(LOCAL/'state.json',dict(state='bounded_owned_Docker_retirement_complete',unmatched_assets_preserved=True))
f.save('image-retirement.json',dict(result='retired_exact_28_unused_recorded_images',removed_images=len(selected),removed_tags=len(record['removed_tags']),private_source_and_image_inspection_records_retained=True,current_app_checkpoint_database_edge_current_and_previous_approved_worker_images_preserved=True,
 current_runtime_17tables_worker_authority_exact=True,all_unselected_image_ids_preserved=True,no_force_no_parent_prune_no_global_prune=True,global_BuildKit_cache_untouched=True,limits='Historical closed fixture images are retired; protected byte-verified volume archives retain data. Current/latest checkpoint recovery roles remain available. Unmatched or ambiguous resources were not selected.'))
print('28 exact unused recorded images retired; all protected/current/unselected images and current data/worker preserved')
