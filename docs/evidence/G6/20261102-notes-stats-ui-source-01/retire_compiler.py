"""Retire exact temporary compiler aliases/image after application derivation."""
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
import driver as d
def call(args):return subprocess.check_output(args,cwd=d.ROOT,timeout=30)
build=d.f.load(d.ROOT/'docs/evidence/G6/20261102-notes-stats-ui-candidate-01/candidate-build.json')
derived=d.f.load(d.ROOT/'docs/evidence/G6/20261102-notes-stats-ui-candidate-02/candidate-build.json')
assert derived['source_image_id']==build['image_id'] and derived['base_layers_python_exact']
assert derived['image_id']!=build['image_id'] and not (d.OUT/'compiler-retirement.json').exists()
assert not call(['docker','ps','--all','--filter','ancestor='+build['image_id'],'--format','{{.ID}}']).strip()
aliases=derived['aliases'];tags=[*aliases,build['tag']]
for tag,expected in zip(tags,[derived['base_image_id'],build['image_id'],build['image_id']]):
    image=json.loads(call(['docker','image','inspect',tag]))[0];assert image['Id']==expected
    assert tag in image['RepoTags']
for tag in tags:call(['docker','image','rm',tag])
remaining=json.loads(call(['docker','image','inspect',derived['image_id']]))[0]
assert remaining['Id']==derived['image_id']
assert json.loads(call(['docker','image','inspect',derived['base_image_id']]))[0]['Id']==derived['base_image_id']
d.f.save('compiler-retirement.json',dict(result='retired_exact_unused_compiler_and_temporary_aliases',removed_tags=tags,
    compiler_image=build['image_id'],current_base_and_admitted_candidate_retained=True,containers_or_volumes_removed=0,no_global_prune=True))
print('Unused compiler and three temporary aliases retired; deployed/checkpoint base and admitted candidate retained')
