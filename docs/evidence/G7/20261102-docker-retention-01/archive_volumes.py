"""Cold archive/verify first, then retire exact unused owned fixture volumes."""
import hashlib,importlib.util,json,subprocess,tarfile
from pathlib import Path,PurePosixPath
OUT=Path(__file__).parent;ROOT=OUT.parents[3];LOCAL=ROOT/'.local/g7-docker-retention'
sp=importlib.util.spec_from_file_location('volume_retention_current',OUT.parent/'20261102-canvas4-source-01/activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
from modular_platform.operator_os import protect_directory
f=m.f;f.OUTPUT=OUT
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=45)
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
def digest(path):
 value=hashlib.sha256()
 with path.open('rb') as stream:
  while chunk:=stream.read(1024*1024):value.update(chunk)
 return value.hexdigest()
assert load(LOCAL/'state.json')['state']=='cold_archive_plan_prepared'
plan=load(LOCAL/'archive-plan.json');assert len(plan['volumes'])==61 and plan['current_project']==m.context()[0]['project']
code_path=OUT/'volume_archive_code.py';code=code_path.read_text();archive_dir=protect_directory(LOCAL/'volume-archives')
marker=LOCAL/'volume-retirement.json';assert not marker.exists()
state,native=m.context();assert native.config['generation']==27 and state['image_id']==plan['archive_helper_image']
before=m.snapshot(state,'retention-volumes-current-before');worker=m.worker(native,'retention-volumes-worker-before')
all_before=set(call(['docker','volume','ls','--format','{{.Name}}']).decode().split())
record=dict(state='archiving_all_sources_before_any_deletion',helper_source_sha256=hashlib.sha256(code.encode()).hexdigest(),volumes={},removed=[]);save(marker,record)
for index,item in enumerate(plan['volumes']):
 name=item['name'];assert name in all_before and not name.startswith(plan['current_project']+'_')
 assert not call(['docker','ps','--all','--filter','volume='+name,'--format','{{.ID}}']).strip()
 info=json.loads(call(['docker','volume','inspect',name]))[0];assert info==item['volume_metadata']
 archive=archive_dir/(name+'.tar.gz');stderr=archive_dir/(name+'.stderr');assert not archive.exists() and not stderr.exists()
 entry=dict(state='archiving',archive=str(archive.relative_to(ROOT)),metadata=item['volume_metadata'],database_images=item['database_images']);record['volumes'][name]=entry;save(marker,record)
 args=['docker','run','--rm','--name','mp-disposable-retention-20261102-'+str(index+1).zfill(2),'--log-driver','none','--label','com.modular.retirement=20261102-docker-retention-01','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','DAC_OVERRIDE','--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--tmpfs','/tmp:rw,nosuid,nodev,size=16m','--mount','type=volume,source='+name+',target=/source,readonly','--entrypoint','/venv/bin/python',plan['archive_helper_image'],'-c',code]
 with archive.open('xb') as output,stderr.open('xb') as error:result=subprocess.run(args,cwd=ROOT,stdout=output,stderr=error,timeout=180)
 assert result.returncode==0,'Archive helper failed; inspect protected original stderr/marker, do not remove or blindly retry source'
 rows=[json.loads(line.split('MP_VOLUME_ARCHIVE=',1)[1]) for line in stderr.read_text().splitlines() if line.startswith('MP_VOLUME_ARCHIVE=')];assert len(rows)==1
 manifest=rows[0]['manifest'];seen=set();data_bytes=0
 with tarfile.open(archive,'r:gz') as stream:
  for member in stream:
   parts=PurePosixPath(member.name).parts;assert parts and parts[0]=='volume' and '..' not in parts and not member.name.startswith('/')
   assert member.name not in seen and member.name in manifest;seen.add(member.name);expected=manifest[member.name]
   assert (member.uid,member.gid,member.mode)==(expected['uid'],expected['gid'],expected['mode']) and abs(member.mtime-expected['mtime_ns']/1e9)<0.000002
   if expected['kind']=='file':
    assert member.isfile() or member.islnk()
    value=hashlib.sha256();size=0
    with stream.extractfile(member) as content:
     while chunk:=content.read(1024*1024):value.update(chunk);size+=len(chunk)
    assert value.hexdigest()==expected['sha256'] and size==expected['size'];data_bytes+=size
   elif expected['kind']=='directory':assert member.isdir()
   else:assert expected['kind']=='symlink' and member.issym() and member.linkname==expected['target']
 assert seen==manifest.keys() and data_bytes==rows[0]['regular_file_bytes']
 manifest_path=archive_dir/(name+'.manifest.json');save(manifest_path,rows[0])
 entry.update(state='archive_verified_source_retained',archive_sha256=digest(archive),archive_bytes=archive.stat().st_size,regular_file_bytes=data_bytes,entries=len(manifest),manifest=str(manifest_path.relative_to(ROOT)));save(marker,record)
 if (index+1)%5==0:print(json.dumps(dict(cold_archives_verified=index+1,total=len(plan['volumes']))),flush=True)
assert len(record['volumes'])==61 and all(v['state']=='archive_verified_source_retained' for v in record['volumes'].values())
record['state']='all_sources_verified_retiring_exact_unused_volumes';save(marker,record)
for item in plan['volumes']:
 name=item['name'];entry=record['volumes'][name]
 assert digest(ROOT/entry['archive'])==entry['archive_sha256']
 assert not call(['docker','ps','--all','--filter','volume='+name,'--format','{{.ID}}']).strip()
 assert json.loads(call(['docker','volume','inspect',name]))[0]==item['volume_metadata']
 record['pending_volume']=name;save(marker,record);call(['docker','volume','rm',name])
 record['removed'].append(name);entry['state']='retired_after_verified_archive';record.pop('pending_volume');save(marker,record)
remaining=set(call(['docker','volume','ls','--format','{{.Name}}']).decode().split());selected={v['name'] for v in plan['volumes']}
assert all_before-selected==remaining and not selected&remaining
assert m.snapshot(state,'retention-volumes-current-after')==before and m.worker(native,'retention-volumes-worker-after')==worker
record['state']='61_volumes_retired_verified_private_archives_retained';save(marker,record)
save(LOCAL/'state.json',dict(state='cold_volumes_retired_image_retention_pending'))
f.save('volume-retirement.json',dict(result='retired_exact_61_unused_owned_volumes_after_verified_cold_archives',removed_volumes=61,all_file_contents_pre_post_hashes_tar_contents_verified=True,ordinary_UID_GID_modes_mtimes_links_verified=True,source_regular_file_bytes=sum(v['regular_file_bytes'] for v in record['volumes'].values()),private_compressed_archive_bytes=sum(v['archive_bytes'] for v in record['volumes'].values()),all_other_volume_names_preserved=True,current_runtime_17tables_worker_authority_recovery_storage_exact=True,unmatched_resources_touched=0,archive_helpers_auto_removed=True,helper_network_none_readonly_source_root_only_DAC_OVERRIDE=True,no_global_prune_or_force=True,limits='Cold byte-verified historical fixture archives are not a rehearsed database restore or permission to replay closed operation approvals. Current/latest actual checkpoint and current/previous worker images retained; exact unused old image cleanup next.'))
print('61 exact unused old fixture volumes archived/file-verified/retired; current and unrelated data/resources unchanged')
