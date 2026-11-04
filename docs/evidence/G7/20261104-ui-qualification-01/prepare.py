"""Prepare one private browser profile and exact current managed target snapshot."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-ui-qualification-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));from modular_platform.operator_os import protect_directory
def load(p):return json.loads(p.read_bytes())
def write(p,v):
 with p.open('x',encoding='utf8') as stream:json.dump(v,stream,indent=2);stream.write('\n')
assert not PRIVATE.exists();protect_directory(PRIVATE);protect_directory(PRIVATE/'profile');OUT.mkdir(exist_ok=True)
local=ROOT/'.local/release-kit-rehearsal/private/reference';state=load(local/'state.json');target=load(local/'operator/target.json');fixture=load(local/'fixtures.json')
assert state['phase']=='kit_backend_worker_reference_qualified' and target['generation']==4 and target['image_id']==state['image_id']
assert target['image_id']==load(ROOT/'docs/evidence/G7/20261104-core23-repro-01/qualification.json')['reference_image']
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership','mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']
query='BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT jsonb_build_object('+','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)+');ROLLBACK;'
raw=subprocess.check_output(['docker','exec',state['project']+'-db-1','psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',state['database'],'-c',query],stderr=subprocess.PIPE);before=json.loads(raw)
assert len(before['mp_example_note'])==2 and len(before['mp_example_canvas_board'])==1 and len(before['mp_job'])==1 and before['mp_job'][0]['state']=='completed'
write(PRIVATE/'tables-before.json',before)
worker=load(local/'worker/qualified-runtime.json')['attestation'];ids=[target['worker_id'],state['project']+'-db-1',state['project']+'-edge-1',worker['container_id']]
rows=json.loads(subprocess.check_output(['docker','inspect',*ids],stderr=subprocess.PIPE));assert all(r['State']['Running'] for r in rows);assert rows[0]['Image']==target['image_id'];write(PRIVATE/'runtimes-before.json',rows)
network=json.loads(subprocess.check_output(['docker','network','inspect',state['project']+'_runtime'],stderr=subprocess.PIPE))[0];assert network['Internal']
record=dict(base=state['url'],database=state['database'],project=state['project'],image_id=target['image_id'],inventory_digest=state['inventory_digest'],generation=4,fixture=fixture,password_file=str(local/'account-passwords.json'),workspace=fixture['workspaces']['A']['public_id'],expected_board_name=before['mp_example_canvas_board'][0]['name'],expected_note_title=before['mp_example_note'][0]['title'],profile=str(PRIVATE/'profile'),node=r'C:\Program Files\nodejs\node.exe',actor='alice')
write(PRIVATE/'browser-input.json',record)
report=dict(result='prepared_exact_current_managed_realm_and_one_owned_profile',utc=datetime.now(timezone.utc).isoformat(),image=record['image_id'],inventory=record['inventory_digest'],generation=4,url=record['base'],native_views_default=True,minimal_Canvas_board=1,notes=2,job_completed=1,private_snapshot_sha256=hashlib.sha256((PRIVATE/'tables-before.json').read_bytes()).hexdigest(),app_network_internal=True,personal_browser_used=False,new_Docker_assets=0,limits=['Preparation only; browser process/measurements/network/ID08/UI09 not yet qualified.'])
write(OUT/'prepared.json',report);print(json.dumps(dict(result=report['result'],image=record['image_id'],url=record['base'])))
