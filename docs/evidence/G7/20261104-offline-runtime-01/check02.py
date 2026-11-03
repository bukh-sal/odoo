"""Current reference runtime under the existing internal-only Docker network."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path.cwd(); OUT=Path(__file__).parent; PRIVATE=ROOT/'.local/g7-offline-runtime-01'
sys.path.insert(0,str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01'))
from lifecycle import f,context,snapshot,worker,LOCAL
from modular_platform.operator_os import protect_directory
import r1_probe
f.OUTPUT=OUT;state,native=context('connector');assert native.config['generation']==5
assert PRIVATE.is_dir()
before=snapshot(state,'offline02-before');identity=worker(native,'offline02-worker-before')
ids=[native.config['worker_id'],identity['id'],state['project']+'-db-1']
containers=json.loads(subprocess.check_output(['docker','inspect',*ids]));observations=[]
networks={}
for item in containers:
 assert item['State']['Running']
 for name,connection in item['NetworkSettings']['Networks'].items():
  info=json.loads(subprocess.check_output(['docker','network','inspect',connection['NetworkID']]))[0]
  assert info['Internal'] and not connection.get('Gateway') and not connection.get('IPv6Gateway')
  networks[name]=dict(id=info['Id'],internal=info['Internal'],driver=info['Driver'])
 observations.append(dict(id=item['Id'],image=item['Image'],name=item['Name'],started=item['State']['StartedAt'],restarts=item['RestartCount'],networks=list(item['NetworkSettings']['Networks'])))
assert len(networks)==1
probe=r'''
import json,socket
rows=[]
for host,port,expected in [('db',5432,True),('app',8069,True),('1.1.1.1',443,False),('8.8.8.8',443,False)]:
 try:
  with socket.create_connection((host,port),timeout=2):connected=True
 except OSError:connected=False
 assert connected==expected,(host,port,connected)
 rows.append(dict(host=host,port=port,connected=connected))
print(json.dumps(rows))
'''
probes={role:json.loads((PRIVATE/(role+'.stdout')).read_bytes()) for role in ['application','worker']}
fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;alice=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob')
document=f.load(ROOT/'docs/evidence/G7/20261104-core22-maintenance-01/state-after.json')
def call(plugin,alias,method,args):
 workspace=fixture['workspaces']['A']['id']
 installation=next(i['installation_id'] for i in document['installations'] if i['plugin_id']==plugin and i['workspace_id']==workspace)
 binding=next(b for b in document['bindings'] if b['consumer_installation_id']==installation and b['workspace_id']==workspace and b['alias']==alias)
 code,response=alice.request('/api/v1/services/'+binding['service_id']+'/'+method,dict(api_version=binding['api_version'],request_id=__import__('uuid').uuid4().hex,input=args),'A',{'X-CSRFToken':alice.csrf,'X-MP-Binding':binding['binding_id']})
 assert code==200,(method,code,response.get('error',{}).get('code'))
 return response['data']
for client,scope in [(alice,'A'),(bob,'B')]:
 assert len(client.call('list',dict(limit=25),scope)['items'])==1
 views=client.native('get_views',workspace=scope,kwargs=dict(views=[[False,'list'],[False,'form']],options={}))
 assert '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
board=call('org.example.canvas','boards','get',{});assert board['revision']==2 and len(board['cards'])==1
note=alice.call('list',dict(limit=25),'A')['items'][0]
job=call('org.example.notes_stats','jobs','status',dict(note_id=note['id']))['job'];assert job['state']=='completed' and job['attempts']==1
ties_path=ROOT/'docs/evidence/G5/20261029-provenance-01/retained-product-ties.json';ties=f.load(ties_path)
runtime=f.load(ROOT/'.local/g7-core22-provenance-01/runtime-observation.json')
for row in ties['records']:assert runtime['inventory']['files'][row['path']]==row['source_sha256']
assert snapshot(state,'offline02-after')==before and worker(native,'offline02-worker-after')==identity;f.guard(state)
record=dict(result='passed_current_internal_only_runtime_reference_reads',image_id=state['image_id'],configuration_generation=5,containers=observations,networks=networks,positive_local_and_negative_external_TCP_probes=probes,native_list_form_two_scopes=True,minimal_Canvas_read=True,existing_completed_reference_job_read=True,retained_Odoo_URL_classification=dict(path=ties_path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(ties_path.read_bytes()).hexdigest(),all_reference_source_hashes_match_current_inventory=True),fresh17tables_worker_original_configs_exact=True,limits=['Actual current application and worker have only internal Docker network and no default gateway; healthy boot and reference backend reads work in that topology.','Read-only current verification; prior ordinary reference job executed with the identical retained worker/network. No new job or CRUD mutation.','No rendered-browser request interception claim. Edge is deliberately dual-homed for inbound local HTTP; browser followable optional links are distinct from backend runtime requirements.','Build-time pinned downloads and optional operator-enabled outbound integrations remain separate documented network uses.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],external_probes_refused=4,local_probes_passed=4,all17tables_unchanged=True)))
