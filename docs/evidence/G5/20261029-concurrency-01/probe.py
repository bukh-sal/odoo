"""Existing scoped APIs/native views, immutable assets and client fence after contention."""
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
import r1_probe


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'http-assets.json';assert not dest.exists()
    state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');config=load(LOCAL/'operator/target.json');marker=load(LOCAL/'concurrency.json')
    assert config['generation']==17 and state['phase']=='concurrency_restored_all_enabled' and marker['state']=='completed_verified'
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];reader=DockerObserver(config);snapshot=Catalog(catalog_root,configuration(trust),readonly=True).snapshot()
    before=load(OUTPUT/'state-before.json');after=load(OUTPUT/'state-after.json');assert reader.state(reader.read(),snapshot)['state']==after
    old=dict(protocol=1,site_id=state['site_id'],generation=15,release_digest=before['release_digest'],inventory_digest=before['release_lock']['core_inventory_digest']);old['token']=data_digest(old)
    checks=[];r1_probe.r1.r0.LOCAL=LOCAL
    for workspace,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor);code,value=client.request('/api/v1/client-release');assert code==200 and value['data']['generation']==17
        code,value=client.request('/api/v1/navigation',workspace=workspace,headers={'X-MP-Client-Release':old['token']});assert code==409 and value['error']['code']=='CONFLICT'
        code,value=client.request('/api/v1/navigation',workspace=workspace);assert code==200
        notes=client.call('list',{'limit':25},workspace)['items'];assert len(notes)==2
        native=client.native('search_read',[[]],{'fields':['public_id','title','body','revision','x_notes_labels']},workspace=workspace);assert len(native)==2 and all(not n['x_notes_labels'] for n in native)
        wid=fixture['workspaces'][workspace]['public_id']
        for plugin,alias,method in [('org.example.canvas','boards','get'),('org.example.notes_labels','labels','set_labels')]:
            install=next(i['installation_id'] for i in after['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
            binding=next(b for b in after['bindings'] if b['consumer_installation_id']==install and b['workspace_id']==wid and b['alias']==alias)
            body=dict(api_version=binding['api_version'],request_id=str(uuid4()),input={})
            if alias=='labels':body.update(idempotency_key=str(uuid4()),input=dict(note_id=notes[0]['id'],expected_revision=notes[0]['revision']+1,labels=['MUST_NOT_CHANGE']))
            code,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,body,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
            if alias=='labels':assert code==409 and value['error']['code']=='CONFLICT'
            else:assert code==200 and len(value['data']['cards'])==1
            checks.append(dict(workspace=workspace,method=method,status=code))
    store=OperatorStore(LOCAL/'operator/control');assets=[];http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    manifests=[store.root/'recoveries/553e16b5-a613-4ec9-a3f9-bda5a0b3d983/assets.json']+[store.root/'stages'/marker['operations'][case]['operation_id']/'assets.json' for case in ['owner','reinstall']]
    for manifest in manifests:
        for asset in load(manifest)['assets']:
            url='http://127.0.0.1:18080'+asset['url']
            with http.open(url,timeout=30) as response:
                assert response.status==200 and response.geturl()==url and 'immutable' in response.headers.get('Cache-Control','')
                assert hashlib.sha256(response.read()).hexdigest()==asset['sha256']
            assets.append(dict(url=asset['url'],sha256=asset['sha256'],immutable=True,redirect=False))
    client=r1_probe.Client(state,fixture,'operator')
    for case in ['owner','reinstall']:
        op=marker['operations'][case]['operation_id'];r=subprocess.run([sys.executable,'-X','utf8','tools/modular.py','--config',str(trust),'operations','--store',str(store.root),'mirror-status',op,'--deployment-config',str(LOCAL/'operator/target.json'),'--catalog',str(catalog_root)],cwd=ROOT,capture_output=True,timeout=120)
        assert r.returncode==0
        code,value=client.request('/api/v1/operations/status/'+op);assert code==200 and value['data']['state']=='completed'
        assert all(d['database_state']=='installed' and d['feature_state']=='enabled' for d in value['data']['dimensions'])
        (OUTPUT/case/'app-status-current.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'business-after.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'schema-after.json')
    assert after==reader.state(reader.read(),snapshot)['state']
    dest.write_text(json.dumps(dict(result='passed',checks=checks,assets=assets,old_publication=old,current_generation=17,old_client_fenced=True,final_business_unchanged_by_probes=True,limits=['Old client pin derived from recorded publication; no pre-existing browser document was observed.','Native Odoo RPC and unchanged native view hosting retained; no new UI behavior or Canvas feature.','Existing read/conflict paths exercised; no committed Labels write or Canvas save.']),indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result='passed',workspaces=2,assets=len(assets),old_client_fenced=True)))


if __name__=='__main__':main()
