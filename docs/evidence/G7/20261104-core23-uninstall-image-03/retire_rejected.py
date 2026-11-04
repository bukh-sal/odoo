"""Retire only the inventoried rejected candidate, with zero-container proof."""
import json
from pathlib import Path
import subprocess

root=Path.cwd();out=Path(__file__).parent
private=root/'.local/g7-core23-uninstall-image-01'
first=root/'docs/evidence/G7/20261104-core23-uninstall-image-01'
build=json.loads((first/'candidate-build.json').read_text());image=build['image_id'];tag=build['tag']
assert image=='sha256:b72ebe5724ee41b478421ec17caa3dc0b47f7bfb7bea828906a592d00eaf4a98'
assert subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()==image
refs=subprocess.check_output(['docker','ps','-aq','--filter','ancestor='+image]).decode().strip()
assert not refs
for filename,command in [('rejected-image-inspect.json',['docker','image','inspect',image]),
                         ('rejected-image-history.jsonl',['docker','history','--no-trunc','--format','{{json .}}',image])]:
    (private/filename).write_bytes(subprocess.check_output(command))
inspect=json.loads((private/'rejected-image-inspect.json').read_text())[0]
assert inspect['RepoTags']==[tag],inspect['RepoTags']
removed=subprocess.run(['docker','image','rm',tag],capture_output=True,check=True,timeout=60)
(private/'rejected-image-removal.stdout').write_bytes(removed.stdout)
assert subprocess.run(['docker','image','inspect',image],capture_output=True,timeout=30).returncode!=0
record=root/'.local/operator/builds/20261104-core23-uninstall-image-02.json'
value=json.loads(record.read_text());assert value['state']=='building'
value.update(state='failed_terminal_no_candidate',failure='Dockerfile FROM bare image ID interpreted as repository; no dependency alias/image/containers created.',
    evidence='docs/evidence/G7/20261104-core23-uninstall-image-02/build.log')
record.write_text(json.dumps(value,indent=2)+'\n')
result=dict(result='rejected_owned_candidate_retired',image_id=image,tag=tag,containers_before=0,
    retained_private_inventory_history=True,current_candidate_and_current_checkpoint_images_retained=True,
    removed_containers_volumes_networks=0,global_prune=False,
    rejected_admission='Unchanged lock but two rebuilt native distributions differ from current qualified dependency bytes; guard retained.',
    failed_second_build='Dockerfile FROM interpreted bare sha256 ID as a registry repository; terminal no image. Unique temporary exact-ID alias fixed in third build and removed.',
    qualified_candidate='sha256:14de369e46f20616e76847cbcacbcb66d5bb791808b950aaf97bc607d31d6b93')
(out/'retirement.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(result=result['result'],images_removed=1,containers_volumes_removed=0)))
