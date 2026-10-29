"""Restored native/API behavior, retained assets and irreversible plan retirement."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files
import r1_probe


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'http-assets-replay.json';assert not dest.exists()
    attempt=OUTPUT/'attempt02';state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');config=load(LOCAL/'operator/target.json')
    assert state['phase']=='executor_crash_restored_resumed' and config['generation']==15
    assert all(load(LOCAL/name)['state']=='completed_verified' for name in ['executor-crash.json','executor-crash02.json'])
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];snapshot=Catalog(catalog_root,configuration(trust),readonly=True).snapshot();reader=DockerObserver(config)
    before=load(attempt/'state-before.json');current=reader.state(reader.read(),snapshot)['state'];business=load(attempt/'business-before.json');schema=load(attempt/'schema-before.json')
    assert current['installations']==before['installations'] and current['bindings']==before['bindings']
    compatibility=dict(protocol=1,site_id=state['site_id'],generation=13,release_digest=before['release_digest'],inventory_digest=before['release_lock']['core_inventory_digest'])
    compatibility['token']=data_digest(compatibility);checks=[];r1_probe.r1.r0.LOCAL=LOCAL
    for workspace,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor);code,value=client.request('/api/v1/client-release');assert code==200 and value['data']['generation']==15
        code,value=client.request('/api/v1/navigation',workspace=workspace,headers={'X-MP-Client-Release':compatibility['token']});assert code==409 and value['error']['code']=='CONFLICT'
        code,value=client.request('/api/v1/navigation',workspace=workspace);assert code==200
        notes=client.call('list',{'limit':25},workspace)['items'];assert len(notes)==2
        rows=client.native('search_read',[[]],{'fields':['public_id','title','revision','body','x_notes_labels']},workspace=workspace);assert len(rows)==2 and all(not r['x_notes_labels'] for r in rows)
        code,value=client.request('/api/v1/context?plugin_id=org.example.notes',workspace=workspace);assert code==200
        wid=fixture['workspaces'][workspace]['public_id']
        for plugin,alias,method in [('org.example.canvas','boards','get'),('org.example.notes_labels','labels','set_labels')]:
            install=next(i['installation_id'] for i in current['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
            binding=next(b for b in current['bindings'] if b['consumer_installation_id']==install and b['workspace_id']==wid and b['alias']==alias)
            payload=dict(api_version=binding['api_version'],request_id=str(uuid4()),input={})
            if alias=='labels':payload.update(idempotency_key=str(uuid4()),input=dict(note_id=notes[0]['id'],expected_revision=notes[0]['revision']+1,labels=['MUST_NOT_CHANGE']))
            status,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
            if alias=='labels':assert status==409 and value['error']['code']=='CONFLICT',(status,value)
            else:assert status==200 and len(value['data']['cards'])==1
            checks.append(dict(workspace=workspace,plugin=plugin,method=method,status=status))
    http=urllib.request.build_opener(urllib.request.ProxyHandler({}));assets=[];store=OperatorStore(LOCAL/'operator/control')
    manifests=[store.root/'stages/4e84908e-4367-49b7-a605-37d199991c69/assets.json']
    manifests += [store.root/'recoveries'/load(LOCAL/name)['operation_id']/'assets.json' for name in ['executor-crash.json','executor-crash02.json']]
    for manifest in manifests:
        for asset in load(manifest)['assets']:
            url='http://127.0.0.1:18080'+asset['url']
            with http.open(url,timeout=30) as response:
                raw=response.read();assert response.status==200 and response.geturl()==url and 'immutable' in response.headers.get('Cache-Control','')
                assert hashlib.sha256(raw).hexdigest()==asset['sha256']
            assets.append(dict(url=asset['url'],sha256=asset['sha256'],immutable=True,redirect=False))
    op=load(LOCAL/'executor-crash02.json')['operation_id'];old_status=store.status(op)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];options=['--deployment-config',str(LOCAL/'operator/target.json'),'--catalog',str(catalog_root)]
    mirror=subprocess.run(prefix+['operations','--store',str(store.root),'mirror-status',op]+options,cwd=ROOT,capture_output=True,timeout=120)
    assert mirror.returncode==0,'Inspect private mirror diagnostics without replaying any native operation'
    client=r1_probe.Client(state,fixture,'operator');code,value=client.request('/api/v1/operations/status/'+op)
    assert code==200 and value['data']['state']=='revoked' and value['data']['phase']=='restore_traffic_resumed',value
    app_status=OUTPUT/'app-status-after-recovery.json'
    if app_status.exists():app_status=OUTPUT/'app-status-after-recovery2.json'
    assert not app_status.exists();app_status.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    replay=subprocess.run(prefix+['plugin','apply',op,'--store',str(store.root)]+options,cwd=ROOT,capture_output=True,timeout=120)
    assert replay.returncode!=0 and b'Retired or completed operation cannot start or continue' in replay.stderr and store.status(op)==old_status
    assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema
    assert files(reader)==load(attempt/'files-restored.json') and reader.state(reader.read(),snapshot)['state']==current
    dest.write_text(json.dumps(dict(result='passed',checks=checks,assets=assets,old_compatibility_document=compatibility,restored_generation=15,old_client_fenced=True,failed_original_plan_replay='denied by permanent independent revocation',exact_business_schema_state_files=True,limits=['Old compatibility pin is deterministically derived from recorded pre-crash publication; no pre-existing browser document was observed in this backend test.','Native Odoo RPC and existing APIs verified; no frontend redesign or Canvas feature expansion.','No successful Labels write/Canvas save; handlers exercised with reads or a deliberately conflicting revision.','No concurrency, dispatch adapter or clean-environment recovery qualification.']),indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result='passed',workspaces=2,assets=len(assets),old_client_fenced=True,failed_plan_replay_denied=True)))


if __name__=='__main__':main()
