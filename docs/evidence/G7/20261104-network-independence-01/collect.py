"""Read actual retained source references and runtime network boundaries only."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;OUT.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_bytes())
def call(args):return subprocess.check_output(args,stderr=subprocess.PIPE,timeout=60)
def write(name,value):
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.write('\n')
reference=ROOT/'.local/release-kit-rehearsal/private/reference';state=load(reference/'state.json');target=load(reference/'operator/target.json');assert target['generation']==4
script=r'''
import collections,hashlib,json,pathlib,re
root=pathlib.Path('/opt/modular');raw=(root/'distribution-inventory.json').read_bytes();inventory=json.loads(raw)
pattern=re.compile(r'(?i)(?:[a-z0-9_-]+\.)*(?:odoo\.(?:com|net)|openerp\.(?:com|net))')
records=[];files=collections.Counter();verified=0
for name,digest in inventory['files'].items():
 path=root/name;data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==digest;verified+=1
 if path.suffix.lower() not in {'.py','.xml','.js','.json','.html','.css','.scss','.md','.rst','.txt','.po','.csv','.svg'}:continue
 try:text=data.decode('utf8')
 except UnicodeError:continue
 matches=[]
 for number,line in enumerate(text.splitlines(),1):
  domains=sorted(set(m.group(0).lower() for m in pattern.finditer(line)))
  if domains:matches.append(dict(line=number,domains=domains))
 if not matches:continue
 category='translation' if '/i18n/' in name else 'test' if '/tests/' in name or '/static/tests/' in name else 'notice_or_documentation' if path.suffix.lower() in {'.md','.rst','.txt'} or path.name.upper() in {'LICENSE','COPYRIGHT','NOTICE'} else 'runtime_source'
 files[category]+=1;records.append(dict(path=name,source_sha256=digest,review_group=category,matches=matches))
print(json.dumps(dict(inventory_digest='sha256:'+hashlib.sha256(raw).hexdigest(),all_inventory_files_verified=verified,native_addons=sorted(inventory['native_addons']),reference_files_by_group=dict(files),records=records)))
'''
references=load(OUT/'retained-reference-candidates.json') if (OUT/'retained-reference-candidates.json').exists() else json.loads(call(['docker','exec',target['worker_id'],'/venv/bin/python','-c',script]));assert references['inventory_digest']==state['inventory_digest']
if not (OUT/'retained-reference-candidates.json').exists():write('retained-reference-candidates.json',references)
worker=load(reference/'worker/qualified-runtime.json')['attestation'];ids=[target['worker_id'],state['project']+'-db-1',state['project']+'-edge-1',worker['container_id']]
rows=json.loads(call(['docker','inspect',*ids]));assert all(r['State']['Running'] for r in rows) and rows[0]['Image']==target['image_id']
network_ids=sorted({v['NetworkID'] for r in rows for v in r['NetworkSettings']['Networks'].values()});networks=json.loads(call(['docker','network','inspect',*network_ids]));by_id={n['Id']:n for n in networks}
for row in [rows[0],rows[1],rows[3]]:assert all(by_id[n['NetworkID']]['Internal'] for n in row['NetworkSettings']['Networks'].values())
assert {n['Name'] for n in networks if not n['Internal']}=={state['project']+'_edge'}
description=[dict(id=r['Id'],image=r['Image'],started_at=r['State']['StartedAt'],networks=sorted(r['NetworkSettings']['Networks']),published_ports=r['NetworkSettings']['Ports']) for r in rows]
# Actual reachability control uses TCP only, no request/body/credentials. The
# expected blocked public connection sends no application data even if it fails.
probe=r'''
import json,pathlib,socket,time
routes=pathlib.Path('/proc/net/route').read_text().splitlines()[1:]
default_routes=sum(line.split()[1]=='00000000' for line in routes if len(line.split())>1)
started=time.monotonic();internal=socket.create_connection(('db',5432),timeout=2);internal.close()
public_blocked=False;error_type=None
try:
 external=socket.create_connection(('1.1.1.1',443),timeout=2);external.close()
except OSError as error:public_blocked=True;error_type=type(error).__name__
assert default_routes==0 and public_blocked
print(json.dumps(dict(app_no_IPv4_default_route=True,internal_database_TCP_succeeded=True,public_TCP_blocked=True,public_control_destination='1.1.1.1:443',public_application_bytes_sent=0,error_type=error_type,elapsed_seconds=round(time.monotonic()-started,3))))
'''
boundary=json.loads(call(['docker','exec',target['worker_id'],'/venv/bin/python','-c',probe]))
write('runtime-network-boundary.json',dict(result='passed_current_internal_network_and_TCP_controls',utc=datetime.now(timezone.utc).isoformat(),image=target['image_id'],generation=4,runtimes=description,networks=[dict(id=n['Id'],name=n['Name'],internal=n['Internal'],driver=n['Driver']) for n in networks],actual_app_controls=boundary,retained_fresh_boot_proof='docs/evidence/G7/20261104-release-kit-01/application-bootstrap.json',retained_reference_worker_job_proof='docs/evidence/G7/20261104-release-kit-01/worker-integration.json',retained_browser_blocked_foreign_control_proof='docs/evidence/G7/20261104-ui-qualification-01/performance-qualification.json',limits=['Read-only runtime inspection/source hash verification/TCP controls. No container restarts, new Docker assets or business mutation.','Browser page-origin interception covers application requests during recorded flows, not Edge background services, OS/host, arbitrary plugins or user-followed external links.','Current reference boot, native/reference UI and worker job are separately evidenced on the same internal-network topology; no repeated bootstrap/job.','Build/package acquisition and optional external user links are distinct network uses.']))
print(json.dumps(dict(result='collected_current_retained_references_and_network_boundary',source_files_verified=references['all_inventory_files_verified'],reference_files=references['reference_files_by_group'],app_database_worker_networks_internal=True,only_edge_ingress_network_noninternal=True,TCP_controls=boundary)))
