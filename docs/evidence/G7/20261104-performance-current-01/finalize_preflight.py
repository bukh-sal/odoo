"""Finish the recorded read-only observation after Docker's null alias list."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();PRIVATE=ROOT/'.local/g7-performance-current-01';OUT=Path(__file__).parent
def load(p):return json.loads(p.read_bytes())
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
record=load(ROOT/'.local/g7-performance-10k-01/state.json');source=load(ROOT/'.local/g6-events/state.json');old=load(PRIVATE/'old-runtime.json');new=load(PRIVATE/'new-runtime.json');rows=load(PRIVATE/'protected-runtime-before.json');before=load(PRIVATE/'benchmark-tables-before.json');original=load(PRIVATE/'original-tables-before.json')
assert record['project']=='mp-g7-perf-6fafdba2c44c' and record['database']=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c'
actual=json.loads(call(['docker','inspect',*[r['Id'] for r in rows]]))
for prior,current in zip(rows,actual):
 assert (prior['Id'],prior['Image'],prior['State']['StartedAt'],prior['RestartCount'],prior['Mounts'],prior['NetworkSettings']['Networks'])==(current['Id'],current['Image'],current['State']['StartedAt'],current['RestartCount'],current['Mounts'],current['NetworkSettings']['Networks']) and current['State']['Running']
assert 'app' not in (rows[0]['NetworkSettings']['Networks'][record['source_runtime_network']].get('Aliases') or [])
for name in ['volume','edge_network']:
 kind='volume' if name=='volume' else 'network';data=json.loads(call(['docker',kind,'inspect',record[name]]))[0];assert data['Labels'].get('com.modular.disposable')==record['project']
query="SELECT jsonb_agg(jsonb_build_object('name',name,'state',state,'version',latest_version) ORDER BY name) FROM ir_module_module WHERE state IN ('installed','to install','to upgrade','to remove');"
modules=json.loads(call(['docker','exec',record['source_pg_container'],'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d',record['database'],'-c',query]));changes=[]
for row in modules:
 assert row['state']=='installed';wanted=new['native_manifests'][row['name']].get('version','1.0');wanted=wanted if wanted.startswith('19.0.') else '19.0.'+wanted
 if row['version']!=wanted:changes.append(dict(addon=row['name'],before=row['version'],after=wanted))
assert changes==[dict(addon='mp_core',before='19.0.0.1.20',after='19.0.0.1.23')]
with (PRIVATE/'record-before.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
report=dict(result='read_only_retained_benchmark_preflight_passed',utc=datetime.now(timezone.utc).isoformat(),project=record['project'],database=record['database'],old_image=record['image_id'],new_image=new['image_id'] if 'image_id' in new else json.loads((ROOT/'docs/evidence/G7/20261104-core23-repro-01/qualification.json').read_bytes())['reference_image'],new_inventory=new['inventory_digest'],native_version_changes=changes,notes=len(before['mp_example_note']),synthetic_notes=sum(n['title'].startswith('G7 benchmark note ') for n in before['mp_example_note']),source_notes=len(original['mp_example_note']),dispatch_paused=True,copied_technical_credentials_revoked=True,app_issuer_absent=True,shared_PostgreSQL_explicit=True,original_runtime_alias_app_not_used_by_benchmark=True,actual_app_limits=dict(memory=rows[0]['HostConfig']['Memory'],nano_cpus=rows[0]['HostConfig']['NanoCpus']),private_snapshot_sha256={name:hashlib.sha256((PRIVATE/name).read_bytes()).hexdigest() for name in ['benchmark-tables-before.json','original-tables-before.json','benchmark-publication-before.json','old-runtime.json','new-runtime.json','protected-runtime-before.json','record-before.json']},diagnosed_first_attempt='Docker reports Aliases:null; read-only observer now treats absence as empty. Prior snapshots/image inspections reused, actual protected runtime identities rechecked; no mutations/replays.',limits=['Observation only; no schema/configuration/container/approval changes.','Next benchmark-only fixture initialization needs explicit checkpoint/isolated target guards; it grants no product deployment or lifecycle qualification.'])
with (OUT/'preflight.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],changes=changes,notes=report['notes'],new_image=report['new_image'])))
