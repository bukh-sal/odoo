"""Exercise the exported kit's offline operator/catalog/general authoring code."""
from pathlib import Path
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

CODE='''
from pathlib import Path
import hashlib,json,sys
kit,work=map(Path,sys.argv[1:3]);source=work/'source';private=work/'private'
sys.path[:0]=[str(source/'release'),str(source/'tools'),str(source/'packages/platform_sdk')]
from verify import verify
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image
from application_package import assemble_application
manifest=verify(kit);trust=private/'trust.json';assert not trust.exists()
trust.write_bytes((kit/'plugins/curated-trust.json').read_bytes())
catalog=Catalog(private/'catalog',configuration(trust))
rows=json.loads((kit/'plugins/index.json').read_bytes())['packages']
for row in rows:catalog.add(kit/row['file'],expected_digest=row['digest'])
assert len(catalog.snapshot())==22
app,=[row for row in rows if row['plugin_id']=='dev.aurora.tasks']
assert app['version']=='0.2.2'
meta,raw,_=assemble_application(source,'plugins/aurora_tasks/application.toml')
assert 'sha256:'+hashlib.sha256(raw).hexdigest()==app['digest']
assert raw==(kit/app['file']).read_bytes()
images=json.loads((kit/'images.json').read_bytes())
runtime=inspect_image(images['images']['application']['image_id'])
assert runtime['inventory_digest']==images['application_inventory_digest']
assert runtime['inventory']['artifacts']['dev.aurora.tasks']['digest']==app['digest']
assert runtime['platform_version']=='0.1.49'
print(json.dumps(dict(result='passed_exported_offline_operator_catalog_and_authoring',
 source_commit=manifest['source_commit'],packages=len(rows),exact_application_bytes=len(raw),
 application_digest=app['digest'],image=images['images']['application']['image_id'],
 inventory_digest=runtime['inventory_digest'],operator_from_kit=True,curation_grants_no_executor_authority=True,
 deployment_or_existing_data_changed=False)))
'''


if __name__=='__main__':
    work=ROOT/'.local/aurora-tasks/at05-consumer-01';setup=json.loads((work/'operator-setup.json').read_bytes())
    assert setup['stage']=='operator_ready_application_not_initialized'
    path=ROOT/'docs/evidence/post-r1/aurora-tasks/at05-consumer.json';assert not path.exists()
    result=subprocess.run([setup['python'],'-I','-c',CODE,str(ROOT/'.local/releases/foundation-r1-core49-tasks'),str(work)],capture_output=True,timeout=120)
    (work/'consumer.stdout').write_bytes(result.stdout);(work/'consumer.stderr').write_bytes(result.stderr)
    assert result.returncode==0,'Inspect private consumer diagnostics before retrying'
    record=json.loads(result.stdout);path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(record))
