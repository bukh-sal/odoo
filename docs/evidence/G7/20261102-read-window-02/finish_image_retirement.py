"""Continue after archived container cleanup; never replay that completed phase."""
import gzip,importlib.util,json,subprocess
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3]
sp=importlib.util.spec_from_file_location('finish_core20_images',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
f=m.f;f.OUTPUT=OUT;state,native=m.context()
assert f.load(OUT/'retirement.json')['removed_containers']==23
assert f.load(m.MARKER)['state']=='preservation_verified'
builds=[f.load(OUT.parent/('20261102-core20-candidate-'+n)/'candidate-build.json') for n in ['01','02','03','04']]
private=ROOT/'.local/retired-docker-20261102/g7-read-window';marker=private/'image-progress.json';assert not marker.exists()
def call(args):return subprocess.check_output(args,cwd=ROOT,timeout=30)
aliases={tag:ident for b in [builds[1],builds[3]] for tag,ident in zip(b['aliases'],[b['base_image_id'],b['source_image_id']])}
for tag in aliases:
 r=subprocess.run(['docker','image','inspect',tag],capture_output=True,timeout=30);assert r.returncode==1
report=dict(state='retiring',already_removed_temporary_aliases=list(aliases),removed_images=[],removed_tags=[]);f.write(marker,report)
for b in builds[:3]:
 ident=b['image_id'];info=json.loads(call(['docker','image','inspect',ident]))[0]
 assert info['RepoTags']==[b['tag']] and info['RepoDigests']==['modular-platform@'+ident]
 assert ident not in (native.config['image_id'],builds[3]['base_image_id'])
 assert not call(['docker','ps','--all','--filter','ancestor='+ident,'--format','{{.ID}}']).strip()
 with gzip.open(private/(ident[7:]+'.image.json.gz'),'wb') as stream:stream.write(json.dumps(info).encode())
 report['pending_image']=ident;f.write(marker,report)
 call(['docker','image','rm','--no-prune',b['tag']])
 assert ident not in set(call(['docker','image','ls','--all','--no-trunc','--format','{{.ID}}']).decode().split())
 report['removed_images'].append(ident);report['removed_tags'].append(b['tag']);report.pop('pending_image');f.write(marker,report)
for ident in [native.config['image_id'],builds[3]['base_image_id']]:assert json.loads(call(['docker','image','inspect',ident]))[0]['Id']==ident
report['state']='completed';f.write(marker,report)
f.save('compiler-retirement.json',dict(result='retired_exact_unused_compilers_superseded_candidate_and_temporary_aliases',removed_tags=[*aliases,*report['removed_tags']],removed_images=3,current_and_checkpoint_retained=True,no_global_prune=True,diagnosis='Original helper conservatively required empty RepoDigests. Docker containerd retains the known local modular-platform@imageID reference on all owned builds; exact ID/tag/build provenance and no-container use validated before unforced tag removal. Completed23container phase and aliases were not replayed.'))
print(json.dumps(dict(removed_images=3,removed_temporary_aliases=len(aliases))))
