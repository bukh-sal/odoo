"""Use the qualified existing resolver and observed exact target metadata.

UV --no-build correctly refuses source-only docopt. No source metadata hooks
are enabled as a workaround. The installed metadata was collected separately
in the controlled, network-free compatibility environment.
"""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-security-locks-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.resolution import resolve_release
from packaging.utils import canonicalize_name
review=json.loads((OUT/'input-review.json').read_text());assert review['result']=='requires_diagnosis'
observed_path=ROOT/'.local/g7-dependency-compatibility-01/final-installed-metadata.stdout'
observed=json.loads(observed_path.read_text())['runtime']
environment=dict(platform_version='0.1.21',native_runtime='odoo-19',markers=observed['markers'],accepted_wheel_tags=observed['accepted_wheel_tags'],core_addons=[])
assert environment['markers']['python_full_version']=='3.12.16'
selection=json.loads((ROOT/'docs/evidence/G7/20261103-dependency-compatibility-01/candidate-selection.json').read_text())
selected={canonicalize_name(p['package']):p for p in selection['candidates']}
def blocks(raw):
 return {canonicalize_name(m[1]):m[0].strip() for m in re.finditer(r'^([A-Za-z0-9_.-]+)==([^\s]+).*?(?=^[A-Za-z0-9_.-]+==|\Z)',raw,re.M|re.S)}
original={label:blocks((ROOT/value['path']).read_text()) for label,value in review['before'].items()}
metadata={canonicalize_name(p['name']):p for p in observed['python_metadata']}
reports=[]
for label,pins in review['pins'].items():
 solution=resolve_release([],observed['python_metadata'],environment,{},core_python=[name+'=='+version for name,version in pins['target'].items()])
 actual={canonicalize_name(p['name']):p['version'] for p in solution['python']}
 assert actual==pins['target'],dict(label=label,unexpected=actual.keys()-pins['target'].keys(),missing=pins['target'].keys()-actual.keys())
 output=[];distributions=[]
 for name,version in sorted(actual.items()):
  # Retain unrelated pins and all their existing verified hash alternatives.
  if name in original[label] and pins['previous'].get(name)==version:
   block='\n'.join(line for line in original[label][name].splitlines() if line.strip() and not line.lstrip().startswith('#'))
   hashes=sorted(re.findall(r'--hash=sha256:([0-9a-f]{64})',block));source='unchanged-qualified-lock'
  elif name=='packaging' and version=='26.3':
   block='\n'.join(line for line in original['r1'][name].splitlines() if line.strip() and not line.lstrip().startswith('#'))
   hashes=sorted(re.findall(r'--hash=sha256:([0-9a-f]{64})',block));source='existing-qualified-R1-lock'
  else:
   candidate=selected[name];assert candidate['version']==version
   path=ROOT/'.local/g7-dependency-compatibility-01'/(name+'-'+version+'.json')
   raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==candidate['metadata_sha256']
   registry=json.loads(raw);assert canonicalize_name(registry['info']['name'])==name and registry['info']['version']==version
   # Hash all non-yanked published distributions, retaining normal pip platform
   # selection. Never introduce an unrecorded local file URL or source command.
   hashes=sorted({item['digests']['sha256'] for item in registry['urls'] if not item.get('yanked')})
   assert hashes and all(re.fullmatch('[0-9a-f]{64}',h) for h in hashes)
   block=name+'=='+version+' \\\n'+' \\\n'.join('    --hash=sha256:'+digest for digest in hashes);source=candidate['source']
  assert hashes
  output.append(block);distributions.append(dict(name=name,version=version,hashes=hashes,source=source,observed_metadata_digest=metadata[name]['digest']))
 raw=('# Reviewed exact security maintenance (ADR0046).\n# Full static solution: docs/evidence/G7/20261103-security-locks-01/static-resolution.json.\n'+'\n'.join(output)+'\n').encode()
 with (PRIVATE/(label+'-static.lock')).open('xb') as f:f.write(raw)
 reports.append(dict(label=label,packages=len(actual),lock_sha256=hashlib.sha256(raw).hexdigest(),distributions=distributions,solution=solution))
report=dict(result='passed_static_complete_solutions',resolver='existing qualified modular_platform.resolution / resolvelib1.2.1',environment=environment,
 observed_metadata_sha256=hashlib.sha256(observed_path.read_bytes()).hexdigest(),solutions=reports,
 no_source_build_hooks_installs_or_canonical_lock_changes=True,
 limits=['Exact versions and registry source hashes only; not installed image/binary reproducibility/provenance/security/lifecycle qualification.',
 'UV --no-build refusal and Python-build availability warning retained. Pure solver uses actual observed full3.12.16 markers, not a substitute interpreter.'])
with (OUT/'static-resolution.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],packages={r['label']:r['packages'] for r in reports})))
