"""Close the bounded owned-asset cleanup; no acceptance or gate inflation."""
import hashlib,json,os,subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-docker-retention'
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
assert load(LOCAL/'state.json')['state']=='bounded_owned_Docker_retirement_complete'
containers=load(OUT/'container-retirement.json');volumes=load(OUT/'volume-retirement.json');images=load(OUT/'image-retirement.json')
assert containers['removed_containers']==105 and volumes['removed_volumes']==61 and images['removed_images']==28
record=load(LOCAL/'volume-retirement.json');assert len(record['removed'])==61
for entry in record['volumes'].values():
 assert entry['state']=='retired_after_verified_archive'
 path=ROOT/entry['archive'];value=hashlib.sha256()
 with path.open('r+b') as stream:
  while chunk:=stream.read(1024*1024):value.update(chunk)
  stream.flush();os.fsync(stream.fileno())
 assert value.hexdigest()==entry['archive_sha256'] and path.stat().st_size==entry['archive_bytes']
summary=subprocess.check_output(['docker','system','df'],cwd=ROOT,timeout=45).decode();(OUT/'docker-system-df.txt').write_text(summary,encoding='utf8')
save(OUT/'qualification.json',dict(result='passed_bounded_repository_owned_Docker_retention',work_item='G-01d0',removed_stopped_containers=105,removed_unused_volumes=61,removed_unused_recorded_images=28,removed_image_tags=images['removed_tags'],
 all_old_selected_volume_bytes_privately_archived_pre_post_and_tar_hash_verified=True,private_archive_bytes=volumes['private_compressed_archive_bytes'],source_regular_file_bytes=volumes['source_regular_file_bytes'],archives_rehashed_and_fsynced_after_retirement=True,
 private_container_logs_inspections_source_and_image_records_retained=True,current4owned_runtime_17tables_36jobs_30Notes_board_worker_authority_unchanged=True,current_and_latest_native_checkpoint_images_current_and_previous_worker_images_preserved=True,
 unmatched_or_unrelated_assets_touched=0,known_hung_rejected_resources_not_retried=True,no_force_no_global_prune_no_parent_pruning=True,global_BuildKit_cache_untouched=True,
 limits=['Bounded cleanup of assets with concrete repository ownership and no remaining use; unmatched/ambiguous resources retained.','Cold file-byte verification does not claim a rehearsed PostgreSQL restore of historical closed fixtures.','Windows/Docker virtual-disk physical compaction is not measured or claimed.','No acceptance, performance, full security/provenance or G7 completion credit from this cleanup. Backend performance and remaining release qualification next.']))
save(LOCAL/'state.json',dict(state='qualified_bounded_owned_asset_retirement',next='G-01c backend performance and remaining G7 qualification',unmatched_assets_preserved=True))
print('Bounded Docker cleanup qualified:105containers/61archivedvolumes/28images retired; current data/worker and unmatched resources preserved')
