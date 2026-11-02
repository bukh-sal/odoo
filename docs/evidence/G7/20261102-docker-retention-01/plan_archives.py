"""Prepare concrete unused-volume/archive and unused-image retention sets."""
import json,re,subprocess
from collections import Counter,defaultdict
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-docker-retention'
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=45)
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
assert load(LOCAL/'state.json')['state']=='terminal_containers_retired_volume_retention_pending'
ownership=load(LOCAL/'ownership.json');known=load(LOCAL/'owned-container-inspections.json');retired=set(load(LOCAL/'container-retirement.json')['removed'])
listed=call(['docker','ps','--all','--no-trunc','--format','{{.ID}}']).decode().split()
users=defaultdict(list)
if listed:
 for line in call(['docker','inspect','--format','{{.Id}} {{json .Mounts}}',*listed]).decode().splitlines():
  ident,raw=line.split(' ',1)
  for mount in json.loads(raw):
   if mount['Type']=='volume':users[mount['Name']].append(ident)
save(LOCAL/'all-current-volume-users.json',dict(users))
former=defaultdict(list)
for info in known:
 for mount in info['Mounts']:
  if mount['Type']=='volume':former[mount['Name']].append(info)
current_project=ownership['protected']['current_project'];selected=[];retained=[]
for volume in load(LOCAL/'owned-volume-inspections.json'):
 name=volume['Name'];old=former[name];labels=volume.get('Labels') or {};project=labels.get('com.docker.compose.project')
 if name.startswith(current_project+'_'):reason='current_project_volume_and_recovery_storage'
 elif users[name]:reason='still_used_by_a_container_including_unmatched_assets'
 elif old and not all(i['Id'] in retired for i in old):reason='former_user_not_retired'
 elif not old and project not in ownership['projects']:reason='no_concrete_former_mount_or_repository_project_label'
 elif any(i['State']['ExitCode']!=0 and 'postgres' in i['Config']['Image'] for i in old):reason='nonclean_database_shutdown_requires_separate_recovery_assessment'
 else:reason=None
 if reason:retained.append(dict(name=name,reason=reason));continue
 assert not users[name] and (old or project in ownership['projects'])
 sql=[i for i in old if 'postgres' in i['Config']['Image']]
 selected.append(dict(name=name,volume_metadata=volume,former_container_ids=[i['Id'] for i in old],former_projects=sorted({(i['Config']['Labels'] or {}).get('com.docker.compose.project') or (i['Config']['Labels'] or {}).get('com.modular.disposable') for i in old}),database_images=sorted({i['Image'] for i in sql}),database_exit_codes=[i['State']['ExitCode'] for i in sql],required_action='cold_archive_verify_then_recheck_unused_before_exact_unforced_removal'))
running_ids=call(['docker','ps','--no-trunc','--format','{{.ID}}']).decode().split()
running_images={line.strip() for line in call(['docker','inspect','--format','{{.Image}}',*running_ids]).decode().splitlines()}
old_worker=load(ROOT/'docs/evidence/G6/20261102-worker-image-success-01/runtime-review.json')['plan']['base_digest']
rejected=load(ROOT/'.local/operator/builds/20261101-core11-candidate-01.json')['image_id']
protected=running_images|{ownership['protected']['current_image'],ownership['protected']['current_checkpoint_image'],old_worker,rejected}
protected|={image for entry in selected for image in entry['database_images']}
image_candidates=[];image_retained=[]
for info in load(LOCAL/'owned-image-inspections.json'):
 ident=info['Id'];tags=info.get('RepoTags') or []
 if ident in protected:reason='current_checkpoint_runtime_database_or_known_rejected_deletion_role'
 elif call(['docker','ps','--all','--filter','ancestor='+ident,'--format','{{.ID}}']).strip():reason='container_user_exists_including_unmatched_assets'
 elif any(not tag.startswith(('modular-platform:','modular-document-stats:')) for tag in tags):reason='unrelated_or_unrecognized_tag'
 else:reason=None
 if reason:image_retained.append(dict(image=ident,reason=reason));continue
 assert ident in ownership['images']
 image_candidates.append(dict(image=ident,tags=tags,metadata=info,source_records=ownership['images'][ident],parent_pruning=False))
plan=dict(state='prepared_not_executed',current_project=current_project,archive_helper_image=ownership['protected']['current_image'],volumes=selected,retained_volumes=retained,images=image_candidates,retained_images=image_retained,protected_images=sorted(protected),unmatched_assets_not_selected=True,global_cache_not_selected=True)
save(LOCAL/'archive-plan.json',plan)
summary=dict(result='exact_archive_retention_plan_prepared_no_deletion',volumes_requiring_private_byte_verified_cold_archive=len(selected),retained_associated_volumes=len(retained),retained_volume_reasons=dict(Counter(v['reason'] for v in retained)),exact_unused_recorded_image_candidates=len(image_candidates),protected_or_used_recorded_images=len(image_retained),unmatched_assets_preserved=True,current_native_and_checkpoint_images_preserved=True,current_and_previous_approved_worker_images_preserved=True,volumes_or_images_deleted=0)
save(OUT/'archive-plan.json',summary);save(LOCAL/'state.json',dict(state='cold_archive_plan_prepared',plan='.local/g7-docker-retention/archive-plan.json'))
print(json.dumps(summary))
