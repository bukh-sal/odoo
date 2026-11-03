"""Retain reproducibility evidence, remove only the unused qualification image."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-second-fresh-build-01'
record=json.loads((OUT/'qualification.json').read_bytes());assert record['result']=='passed_second_fresh_no_cache_declared_inventory'
image=record['image_id'];assert image!=record['baseline_image']
info=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]
assert info['Id']==image and info['RepoTags']==[record['tag']]
assert not subprocess.check_output(['docker','ps','-aq','--filter','ancestor='+image]).strip()
raw=json.dumps(info,indent=2).encode();(PRIVATE/'retired-image-inspect.json').write_bytes(raw)
history=subprocess.check_output(['docker','history','--no-trunc','--format','{{json .}}',image]);(PRIVATE/'retired-image-history.jsonl').write_bytes(history)
subprocess.run(['docker','image','rm',record['tag']],capture_output=True,check=True,timeout=60)
gone=subprocess.run(['docker','image','inspect',image],capture_output=True,timeout=20);assert gone.returncode and b'no such' in gone.stderr.lower()
assert subprocess.check_output(['docker','image','inspect',record['baseline_image'],'--format','{{.Id}}']).decode().strip()==record['baseline_image']
result=dict(result='retired_unused_second_fresh_build_image',image_id=image,tag=record['tag'],containers_using_image=0,inspect_sha256=hashlib.sha256(raw).hexdigest(),history_sha256=hashlib.sha256(history).hexdigest(),baseline_current_and_checkpoint_images_retained=True,images_removed=1,containers_volumes_networks_removed=0,build_cache='No global builder prune; shared Docker build cache not indiscriminately removed.')
with (OUT/'retirement.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],images_removed=1)))
