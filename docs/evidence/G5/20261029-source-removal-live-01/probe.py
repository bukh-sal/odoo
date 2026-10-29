"""Read-only survivor/API/immutable asset qualification after actual removal."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
import r1_probe


def main():
    destination=OUTPUT/'survivor-http-assets.json';assert not destination.exists()
    state=json.loads((LOCAL/'state.json').read_text());fixture=json.loads((LOCAL/'fixtures.json').read_text())
    config=json.loads((LOCAL/'operator/target.json').read_text())
    assert state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==9
    assert state['phase']=='artifact_source_removed'
    reader=DockerObserver(config);catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    observed=reader.state(reader.read(),catalog)['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    assert business==json.loads((OUTPUT/'remove/business-after.json').read_text())
    old=json.loads((OUTPUT/'uninstall/state-before.json').read_text());r1_probe.r1.r0.LOCAL=LOCAL;checks=[]
    for workspace,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor);wid=fixture['workspaces'][workspace]['public_id']
        notes=client.call('list',{'limit':25},workspace)['items'];assert len(notes)==2
        rows=client.native('search_read',[[]],{'fields':['public_id','title','revision','body']},workspace=workspace)
        assert {n['id'] for n in notes}=={n['public_id'] for n in rows}
        assert 'x_notes_labels' not in client.native('fields_get',[],{'attributes':['type']},workspace=workspace)
        status,slots=client.request('/api/v1/ui/slot?slot_id=org.example.notes:slot:detail_actions&major=1',workspace=workspace)
        assert status==200 and slots['data']==[]
        for plugin,alias,method in [('org.example.canvas','boards','get'),('org.example.notes_labels','labels','set_labels')]:
            source=old if alias=='labels' else observed
            install=next(i['installation_id'] for i in source['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
            binding=next(b for b in source['bindings'] if b['consumer_installation_id']==install and b['workspace_id']==wid and b['alias']==alias)
            payload=dict(api_version=binding['api_version'],request_id=str(uuid4()),input={})
            if alias=='labels':payload.update(idempotency_key=str(uuid4()),input=dict(note_id=notes[0]['id'],expected_revision=notes[0]['revision'],labels=['MUST_NOT_CHANGE']))
            status,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
            if alias=='labels':assert status==503 and value['error']['code']=='DEPENDENCY_UNAVAILABLE',(status,value)
            else:assert status==200 and len(value['data']['cards'])==1
            checks.append(dict(workspace=workspace,plugin=plugin,method=method,status=status,code=value.get('error',{}).get('code')))
    assets=[];http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    control=LOCAL/'operator/control'
    operations=['9958f09b-9181-41aa-99d4-2953a3e3095d']+[json.loads((LOCAL/('source-live-'+case+'.json')).read_text())['operation_id'] for case in ['uninstall','remove']]
    for operation in operations:
        for asset in json.loads((control/'stages'/operation/'assets.json').read_text())['assets']:
            url='http://127.0.0.1:18080'+asset['url']
            with http.open(url,timeout=30) as response:
                body=response.read();assert response.status==200 and response.geturl()==url
                assert hashlib.sha256(body).hexdigest()==asset['sha256'] and len(body)==asset['bytes']
                assert 'immutable' in response.headers.get('Cache-Control','')
            assets.append(dict(operation=operation,url=asset['url'],sha256=asset['sha256'],status=200,redirect=False,immutable=True))
    assert business==json.loads(sql(reader,BUSINESS_SQL)) and schema==json.loads(sql(reader,SCHEMA))
    assert observed==reader.state(reader.read(),catalog)['state']
    with destination.open('x',encoding='utf8') as f:f.write(json.dumps(dict(result='passed',checks=checks,assets=assets,notes_native_and_gateway=True,removed_native_field_absent=True,removed_slot_absent=True,all_state_schema_business_exact=True,limits=['Read-only survivor proof; Canvas save/conflict and permission-expanding upgrade are separate requirements.']),indent=2)+'\n')
    print(json.dumps(dict(result='passed',workspaces=2,assets=len(assets),supported_labels_command_denied=True)))


if __name__=='__main__':main()
