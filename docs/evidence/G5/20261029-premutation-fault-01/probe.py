"""Actual base compatibility, scoped API/assets and failed-plan replay refusal."""
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
    state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');config=load(LOCAL/'operator/target.json');assert state['phase']=='premutation_unchanged_resumed' and config['generation']==11
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];snapshot=Catalog(catalog_root,configuration(trust),readonly=True).snapshot();reader=DockerObserver(config)
    before=load(OUTPUT/'state-before.json');assert reader.state(reader.read(),snapshot)['state']==before
    business=load(OUTPUT/'business-before.json');schema=load(OUTPUT/'schema-before.json');r1_probe.r1.r0.LOCAL=LOCAL
    compatibility=dict(protocol=1,site_id=state['site_id'],generation=11,release_digest=before['release_digest'],inventory_digest=before['release_lock']['core_inventory_digest'])
    compatibility['token']=data_digest(compatibility);checks=[]
    for workspace,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor);code,value=client.request('/api/v1/client-release');assert code==200 and value['data']==compatibility
        code,value=client.request('/api/v1/navigation',workspace=workspace,headers={'X-MP-Client-Release':compatibility['token']});assert code==200
        notes=client.call('list',{'limit':25},workspace)['items'];assert len(notes)==2
        rows=client.native('search_read',[[]],{'fields':['public_id','title','revision','body','x_notes_labels']},workspace=workspace);assert len(rows)==2
        wid=fixture['workspaces'][workspace]['public_id']
        for plugin,alias,method in [('org.example.canvas','boards','get'),('org.example.notes_labels','labels','set_labels')]:
            install=next(i['installation_id'] for i in before['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
            binding=next(b for b in before['bindings'] if b['consumer_installation_id']==install and b['workspace_id']==wid and b['alias']==alias)
            payload=dict(api_version=binding['api_version'],request_id=str(uuid4()),input={})
            if alias=='labels':payload.update(idempotency_key=str(uuid4()),input=dict(note_id=notes[0]['id'],expected_revision=notes[0]['revision']+1,labels=['MUST_NOT_CHANGE']))
            status,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
            if alias=='labels':assert status==409 and value['error']['code']=='CONFLICT',(status,value)
            else:assert status==200 and len(value['data']['cards'])==1
            checks.append(dict(workspace=workspace,plugin=plugin,method=method,status=status))
    http=urllib.request.build_opener(urllib.request.ProxyHandler({}));assets=[]
    for operation in ['9958f09b-9181-41aa-99d4-2953a3e3095d','ebc94319-33ae-4860-9cf5-cc74e30ef95c','4e84908e-4367-49b7-a605-37d199991c69']:
        for asset in load(LOCAL/'operator/control/stages'/operation/'assets.json')['assets']:
            url='http://127.0.0.1:18080'+asset['url']
            with http.open(url,timeout=30) as response:
                raw=response.read();assert response.status==200 and response.geturl()==url and 'immutable' in response.headers.get('Cache-Control','')
                assert hashlib.sha256(raw).hexdigest()==asset['sha256']
            assets.append(dict(url=asset['url'],sha256=asset['sha256'],immutable=True,redirect=False))
    store=OperatorStore(LOCAL/'operator/control');op=load(LOCAL/'premutation-fault.json')['operation_id'];old_status=store.status(op)
    replay=subprocess.run([sys.executable,'-X','utf8','tools/modular.py','--config',str(trust),'plugin','apply',op,'--store',str(store.root),'--deployment-config',str(LOCAL/'operator/target.json'),'--catalog',str(catalog_root)],cwd=ROOT,capture_output=True,timeout=120)
    assert replay.returncode!=0 and b'approval is revoked' in replay.stderr and store.status(op)==old_status
    assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema and files(reader)==load(OUTPUT/'files-before.json')
    assert reader.state(reader.read(),snapshot)['state']==before
    dest.write_text(json.dumps(dict(result='passed',checks=checks,assets=assets,unchanged_compatibility_document=compatibility,failed_original_plan_replay='denied by permanent independent revocation',exact_business_schema_state_files=True,limits=['Compatibility pin is deterministically derived from recorded pre-fault publication; no pre-existing browser document was observed through this backend-only test.','No successful Labels write/Canvas save; handlers are exercised with reads or a deliberately conflicting revision.','No OS-process crash or dispatch adapter qualification.']),indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result='passed',workspaces=2,assets=len(assets),unchanged_compatibility=True,failed_plan_replay_denied=True)))


if __name__=='__main__':main()
