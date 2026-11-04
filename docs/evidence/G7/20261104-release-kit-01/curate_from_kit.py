"""Use only the kit-installed interpreter/SDK to create a new verified artifact catalog."""
import json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;WORK=ROOT/'.local/release-kit-rehearsal';KIT=ROOT/'.local/releases/r1-0.1.23'
state=json.loads((WORK/'operator-setup.json').read_bytes());assert state['stage']=='operator_ready_application_not_initialized'
assert not (WORK/'private/catalog').exists()
code="""import json,sys
from pathlib import Path
source,kit,private=map(Path,sys.argv[1:]);sys.path[:0]=[str(source/'tools'),str(source/'packages/platform_sdk')]
from modular import configuration
from modular_platform.operator_os import verify_private_directory
from modular_platform.catalog import Catalog
verify_private_directory(private)
config=configuration(kit/'plugins/curated-trust.json');catalog=Catalog(private/'catalog',config)
index=json.loads((kit/'plugins/index.json').read_bytes())['packages']
for row in index:catalog.add(kit/row['file'],expected_digest=row['digest'])
rows=catalog.snapshot();assert len(rows)==len(index)==19
assert {r['digest'] for r in rows}=={r['digest'] for r in index}
print(json.dumps(dict(result='created_new_catalog_from_verified_kit_archives',packages=len(rows),digests=sorted(r['digest'] for r in rows),no_operator_store_or_approval_created=True)))
"""
r=subprocess.run([state['python'],'-I','-c',code,state['source'],str(KIT),state['private']],capture_output=True,timeout=60)
for suffix,raw in [('stdout',r.stdout),('stderr',r.stderr)]: (ROOT/'.local/g7-release-kit-01'/('catalog-from-kit.'+suffix)).write_bytes(raw)
assert r.returncode==0,'Inspect partial catalog/diagnostic; no blind reimport'
observed=json.loads(r.stdout)
with (OUT/'catalog-from-kit.json').open('x',encoding='utf8') as f:json.dump(observed,f,indent=2);f.write('\n')
print(json.dumps(dict(result=observed['result'],packages=19)))
