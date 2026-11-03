"""Finish successful static records after local notice-loop variable shadowing."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-source-notices-01'
sys.path.insert(0,str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'))
from lifecycle import f as factory,context
factory.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==4
load=lambda p:json.loads(p.read_text());official=load(OUT/'official-source.json');notices=load(OUT/'notice-bundle.json');artifacts=load(OUT/'artifact-provenance.json')
assert official['result']=='passed' and notices['result']=='passed_preserved' and artifacts['result'].startswith('passed') and len(artifacts['artifacts'])==19
assert hashlib.sha256((PRIVATE/'release-notices.zip').read_bytes()).hexdigest()==notices['archive_sha256'];factory.guard(state)
record=dict(result='passed_current_official_source_and_application_notices_and19archives',utc=datetime.now(timezone.utc).isoformat(),application_image=state['image_id'],inventory_digest=state['inventory_digest'],records_sha256={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['official-source.json','notice-bundle.json','artifact-provenance.json']},python_distributions=notices['python_distributions'],OS_packages=notices['OS_packages'],native_addons=notices['native_addons'],curated_archives=19,deployment_mutations=0,images_built=0,continuation_reason='First audit completed all static records before its local notice-loop f dictionary shadowed the fixture alias at final guard; no runtime/source defect or repeated build.',limits=['Static source/notice subset only; not fullOPS03 or final G7/security/legal compatibility opinion.','Worker/support image notices, vendored components, advisories/network/history/layers/archives/secrets/reprobuild/release-kit still require current evidence.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],Python=record['python_distributions'],OS=record['OS_packages'],archives=19)))
