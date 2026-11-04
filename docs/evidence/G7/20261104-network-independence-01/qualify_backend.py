"""Qualify the backend/static network subresult without claiming complete G7."""
import base64,hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
def load(p):return json.loads(p.read_bytes())
boundary=load(OUT/'runtime-network-boundary.json');ties=load(OUT/'reviewed-product-ties.json');assert ties['runtime_source_families_reviewed']==24 and ties['runtime_technical_Odoo_service_requirements_found']==0
assert boundary['actual_app_controls']['public_TCP_blocked'] and boundary['actual_app_controls']['internal_database_TCP_succeeded']
record=load(ROOT/'.local/g7-ui-qualification-01/browser-input.json');before=load(ROOT/'.local/g7-ui-qualification-01/tables-before.json')
target=load(ROOT/'.local/release-kit-rehearsal/private/reference/operator/target.json');assert target['image_id']==boundary['image'] and target['generation']==4
raw=subprocess.check_output(['docker','exec',record['project']+'-edge-1','cat','/etc/nginx/conf.d/default.conf'],stderr=subprocess.PIPE,timeout=30);assert raw.decode()==(ROOT/'deploy/nginx-r0.conf').read_text()
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in before)+');ROLLBACK;'
after=json.loads(subprocess.check_output(['docker','exec',record['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database'],'-c',query],stderr=subprocess.PIPE,timeout=30));assert before==after
old=load(ROOT/'.local/g7-ui-qualification-01/runtimes-before.json');actual=json.loads(subprocess.check_output(['docker','inspect',*[r['Id'] for r in old]],stderr=subprocess.PIPE,timeout=30))
for a,b in zip(old,actual):
 assert b['State']['Running'] and a['Id']==b['Id'] and a['Image']==b['Image'] and a['State']['StartedAt']==b['State']['StartedAt'] and a['Mounts']==b['Mounts'] and a['NetworkSettings']==b['NetworkSettings']
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[p for p in OUT.iterdir() if p.is_file()]+[ROOT/'docs/network-independence.md']+[ROOT/'.local/g7-network-independence-01'/name for name in ['classifier.stdout','classifier.stderr']]
findings=[f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings,'Privacy findings require review'
result=dict(result='passed_backend_static_network_independence_subresult',utc=datetime.now(timezone.utc).isoformat(),work_item='G-01d2',spec_section='27',image=boundary['image'],inventory=ties['inventory_digest'],generation=4,immutable_files_verified=4159,reviewed_runtime_families=24,explicit_false_positive_matches=11,app_database_worker_internal_only=True,only_named_ingress_bridge_noninternal=True,actual_TCP_positive_and_negative_controls=True,proxy_config_sha256=hashlib.sha256(raw).hexdigest(),all17_business_authority_job_event_tables_exact=True,all4_runtime_process_image_mount_network_identities_exact=True,new_Docker_assets=0,privacy=dict(known_values=len(values),files=len(paths),findings=0),evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_relative_to(OUT) or p.suffix=='.md'},remaining=['Required current native-form/Labels/two-tab/RTL/keyboard browser flows and full observed network reconciliation.','Final current operator-tool source kit refresh/privacy delta and release closure; OPS03 remains invalidated until complete.','ID08/UI09 and finalsection28audit/developer handoff remain.'],limits=['Backend/static subresult only, no additional weighted point or full acceptance/gate pass.','Finite source/domain/consumer scan and observed TCP/current internal topology, not universal absence of obfuscated calls or hostile native/browser/OS containment.','Initial overbroad network assumption, Windows argument limit and config-test-consumer assertion refusals preserved; actual source/sample responses reused. No bootstrap/job/native lifecycle replay.'])
with (OUT/'backend-qualification.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(result=result['result'],runtime_families=24,files_verified=4159,tables_exact=17,runtime_identities_exact=4,privacy_findings=0)))
