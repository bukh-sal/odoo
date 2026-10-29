"""Read-only positive/negative scoped probes after each exact lifecycle operation."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];LOCAL=ROOT/'.local/g5-lifecycle';OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
import r1_probe


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['A-only','all-enabled']);args=parser.parse_args()
    dest=OUTPUT/('probe-'+args.mode+'.json');assert not dest.exists()
    state=json.loads((LOCAL/'state.json').read_text());fixture=json.loads((LOCAL/'fixtures.json').read_text())
    config=json.loads((LOCAL/'operator/target.json').read_text())
    assert state['project']==config['project']=='mp-r0-r1lifef99acae9d906' and config['generation']==6
    assert state['phase']==('labels_reinstalled_A' if args.mode=='A-only' else 'lifecycle_reinstalled_all_enabled')
    reader=DockerObserver(config);catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    observed=reader.state(reader.read(),catalog)['state'];business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA))
    r1_probe.r1.r0.LOCAL=LOCAL;checks=[]
    for workspace,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor);suspended=workspace=='B' and args.mode=='A-only'
        notes=client.call('list',{'limit':25},workspace)['items'];assert len(notes)==2
        assert all(n['labels']==[] for n in notes)
        status,context=client.request('/api/v1/context?plugin_id=org.example.notes_labels',workspace=workspace)
        assert status==(409 if suspended else 200),(workspace,status,context)
        if suspended:assert context['error']['code']=='PLUGIN_SUSPENDED'
        else:assert [c['id'] for c in context['data']['commands']]==['org.example.notes_labels:command:set_labels']
        status,slots=client.request('/api/v1/ui/slot?slot_id=org.example.notes:slot:detail_actions&major=1',workspace=workspace)
        assert status==200 and len(slots['data'])==(0 if suspended else 1)
        rows=client.native('search_read',[[('public_id','=',notes[0]['id'])]],{'fields':['id','public_id','title','revision']},workspace=workspace)
        assert len(rows)==1
        if suspended:
            installation=next(i['installation_id'] for i in observed['installations'] if i['plugin_id']=='org.example.notes_labels' and i['workspace_id']==fixture['workspaces'][workspace]['public_id'])
            binding=next(b for b in observed['bindings'] if b['consumer_installation_id']==installation and b['workspace_id']==fixture['workspaces'][workspace]['public_id'] and b['alias']=='labels')
            status,denied=client.request('/api/v1/services/'+binding['service_id']+'/set_labels',dict(api_version=binding['api_version'],request_id=str(uuid4()),idempotency_key=str(uuid4()),
                input=dict(note_id=notes[0]['id'],expected_revision=notes[0]['revision'],labels=['MUST_NOT_CHANGE'])),workspace=workspace,headers={'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
            assert status==409 and denied['error']['code']=='PLUGIN_SUSPENDED',(status,denied)
            client.native('read',[[rows[0]['id']],['x_notes_labels']],workspace=workspace,deny=True)
            client.native('write',[[rows[0]['id']],{'x_notes_labels':['MUST_NOT_CHANGE']}],{'context':{'expected_revision':rows[0]['revision']}},workspace=workspace,deny=True)
        else:
            fields=client.native('read',[[rows[0]['id']],['x_notes_labels']],workspace=workspace)
            assert fields[0]['x_notes_labels'] in (False,[],None)
        install=next(i['installation_id'] for i in observed['installations'] if i['plugin_id']=='org.example.canvas' and i['workspace_id']==fixture['workspaces'][workspace]['public_id'])
        binding=next(b for b in observed['bindings'] if b['consumer_installation_id']==install and b['workspace_id']==fixture['workspaces'][workspace]['public_id'] and b['alias']=='boards')
        status,board=client.request('/api/v1/services/'+binding['service_id']+'/get',dict(api_version=binding['api_version'],request_id=str(uuid4()),input={}),workspace=workspace,headers={'X-CSRFToken':client.csrf,'X-MP-Binding':binding['binding_id']})
        assert status==200 and len(board['data']['cards'])==1
        checks.append(dict(workspace=workspace,labels_suspended=suspended,notes_native_and_gateway=True,canvas_get=True,
                           context_commands_slots=True,explicit_native_labels_access=('denied read/write' if suspended else 'allowed read'),
                           supported_set_labels_dispatch=('409 PLUGIN_SUSPENDED' if suspended else 'not invoked to preserve revisions')))
    assert business==json.loads(sql(reader,BUSINESS_SQL)) and schema==json.loads(sql(reader,SCHEMA))
    assert observed==reader.state(reader.read(),catalog)['state']
    with dest.open('x',encoding='utf8') as f:f.write(json.dumps(dict(result='passed_'+args.mode,checks=checks,all_state_schema_business_exact=True,
        limits=['No successful Labels writes/Canvas saves in this read-only regression; their unchanged package behavior is covered by existing reference-plugin tests.']),indent=2)+'\n')
    print(json.dumps(dict(result='passed_'+args.mode,workspaces=2,data_unchanged=True)))


if __name__=='__main__':main()
