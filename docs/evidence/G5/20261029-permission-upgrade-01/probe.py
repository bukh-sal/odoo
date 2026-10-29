"""Scoped existing handlers and immutable assets after actual permission upgrade."""
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
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    dest=OUTPUT/'survivor-http-assets.json';assert not dest.exists()
    state=load(LOCAL/'state.json');fixture=load(LOCAL/'fixtures.json');config=load(LOCAL/'operator/target.json');meta=load(OUTPUT/'catalog.json')
    assert state['phase']=='permission_upgrade_completed' and config['generation']==11 and config['project']=='mp-r0-r1lifef99acae9d906'
    catalog=Catalog(ROOT/meta['paths']['catalog'],configuration(ROOT/meta['paths']['trust']),readonly=True).snapshot()
    reader=DockerObserver(config);observed=reader.state(reader.read(),catalog)['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    assert business==load(OUTPUT/'upgrade/business-after.json') and ['mp_example_notes_labels','installed','19.0.0.2.2'] in schema['native']
    r1_probe.r1.r0.LOCAL=LOCAL;checks=[]
    for workspace,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor);wid=fixture['workspaces'][workspace]['public_id']
        notes=client.call('list',{'limit':25},workspace)['items'];assert len(notes)==2 and all(n['labels']==[] for n in notes)
        rows=client.native('search_read',[[]],{'fields':['public_id','title','revision','body','x_notes_labels']},workspace=workspace)
        assert {n['id'] for n in notes}=={n['public_id'] for n in rows} and all(n['x_notes_labels'] in (False,None,[]) for n in rows)
        status,context=client.request('/api/v1/context?plugin_id=org.example.notes_labels',workspace=workspace)
        assert status==200 and [c['id'] for c in context['data']['commands']]==['org.example.notes_labels:command:set_labels']
        status,slot=client.request('/api/v1/ui/slot?slot_id=org.example.notes:slot:detail_actions&major=1',workspace=workspace)
        assert status==200 and len(slot['data'])==1
        for plugin,alias,method in [('org.example.canvas','boards','get'),('org.example.notes_labels','labels','set_labels')]:
            install=next(i['installation_id'] for i in observed['installations'] if i['plugin_id']==plugin and i['workspace_id']==wid)
            binding=next(b for b in observed['bindings'] if b['consumer_installation_id']==install and b['workspace_id']==wid and b['alias']==alias)
            payload=dict(api_version=binding['api_version'],request_id=str(uuid4()),input={})
            if alias=='labels':payload.update(idempotency_key=str(uuid4()),input=dict(note_id=notes[0]['id'],expected_revision=notes[0]['revision']+1,labels=['MUST_NOT_CHANGE']))
            status,value=client.request('/api/v1/services/'+binding['service_id']+'/'+method,payload,workspace,{'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
            if alias=='labels':assert status==409 and value['error']['code']=='CONFLICT',(status,value)
            else:assert status==200 and len(value['data']['cards'])==1
            checks.append(dict(workspace=workspace,plugin=plugin,method=method,status=status,code=value.get('error',{}).get('code')))
    http=urllib.request.build_opener(urllib.request.ProxyHandler({}));assets=[]
    operations=['9958f09b-9181-41aa-99d4-2953a3e3095d',load(LOCAL/'permission-restore.json')['operation_id'],load(LOCAL/'permission-upgrade.json')['operation_id']]
    for operation in operations:
        for asset in load(LOCAL/'operator/control/stages'/operation/'assets.json')['assets']:
            url='http://127.0.0.1:18080'+asset['url']
            with http.open(url,timeout=30) as response:
                raw=response.read();assert response.status==200 and response.geturl()==url
                assert hashlib.sha256(raw).hexdigest()==asset['sha256'] and len(raw)==asset['bytes'] and 'immutable' in response.headers.get('Cache-Control','')
            assets.append(dict(operation=operation,url=asset['url'],sha256=asset['sha256'],status=200,redirect=False,immutable=True))
    assert business==json.loads(sql(reader,BUSINESS_SQL)) and schema==json.loads(sql(reader,SCHEMA)) and observed==reader.state(reader.read(),catalog)['state']
    dest.write_text(json.dumps(dict(result='passed',checks=checks,assets=assets,native_gateway_slots_commands=True,business_schema_metadata_exact=True,limits=['Labels command exercised with a deliberately conflicting revision and no committed business change; no new handler or Canvas save/product feature.','Integration grant metadata is not containment for trusted native Python.']),indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(result='passed',workspaces=2,assets=len(assets),supported_labels_conflict_preserved=True)))


if __name__=='__main__':main()
