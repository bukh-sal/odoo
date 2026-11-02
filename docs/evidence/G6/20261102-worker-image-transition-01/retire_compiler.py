"""Retire the rejected compiler image and build aliases, preserving real roles."""
import gzip,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory

def call(args):return subprocess.check_output(args,timeout=30)
def inspect(ident):return json.loads(call(['docker','image','inspect',ident]))[0]
source=json.loads((ROOT/'docs/evidence/G6/20261102-core17-candidate-01/candidate-build.json').read_text())
derived=json.loads((ROOT/'docs/evidence/G6/20261102-core17-candidate-02/candidate-build.json').read_text())
assert derived['base_os_python_layers_exact'] and derived['python_distributions_exact'] and derived['native_core_changes']==[dict(addon='mp_core',previous_version='19.0.0.1.16',target_version='19.0.0.1.17',migrations=[])]
target=json.loads((ROOT/'.local/g6-events/operator/target.json').read_text());assert target['generation']==19
rejected=source['image_id'];base=target['image_id'];candidate=derived['image_id'];assert rejected not in (base,candidate)
source_alias='modular-platform:core17-source-'+rejected[7:];base_alias='modular-platform:core17-base-'+base[7:]
row=inspect(rejected);assert set(row['RepoTags'])=={source['tag'],source_alias}
assert inspect(source_alias)['Id']==rejected and inspect(base_alias)['Id']==base
assert not call(['docker','ps','--all','-q','--filter','ancestor='+rejected]).strip()
assert inspect(candidate)['RootFS']['Layers'][:len(inspect(base)['RootFS']['Layers'])]==inspect(base)['RootFS']['Layers']
archive=protect_directory(ROOT/'.local/retired-docker-20261102/core17-rejected-compiler')
with gzip.open(archive/(rejected[7:]+'.json.gz'),'xb') as stream:stream.write(json.dumps(row).encode())
call(['docker','image','rm',source['tag'],source_alias,base_alias])
gone=subprocess.run(['docker','image','inspect',rejected],capture_output=True,timeout=15);assert gone.returncode!=0
assert inspect(base)['Id']==base and inspect(candidate)['Id']==candidate
(OUT/'rejected-retirement.json').write_text(json.dumps(dict(result='retired_exact_rejected_unrequested_binary_candidate',removed_images=1,
    removed_temporary_build_aliases=2,rejected_image=rejected,current_base_and_admitted_candidate_preserved=True,
    no_attached_containers_or_other_tags=True,private_diagnostics_retained=True,no_global_prune_or_force=True,
    original_build_recipe_source_commit_and_deterministic_archives_retained=True),indent=2)+'\n',encoding='utf8')
print('Rejected compiler image and2temporary aliases retired; current and admitted candidate/checkpoint roles preserved')
