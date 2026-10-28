"""Idempotent scoped business fixtures for G5 upgrade/recovery qualification."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import r1_probe
import r1

ROOT=Path(__file__).resolve().parents[1]
r1.r0.LOCAL=ROOT/'.local/g5'


def main():
    import sys
    sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
    from modular_platform.catalog import Catalog
    from modular_platform.deployment import DockerObserver
    from modular_platform.operator_store import OperatorStore
    from modular_platform.plans import data_digest
    from modular import configuration
    local=r1.r0.LOCAL;state=json.loads((local/'state.json').read_text())
    config=json.loads((ROOT/'.local/operator/targets/g5.json').read_text())
    assert state['profile']=='G5' and state['disposable'] and state['active_db']==config['sites'][0]['database']
    marker=local/'lifecycle-data.json'
    if marker.exists():
        saved=json.loads(marker.read_text())
        if saved['state']=='completed':raise RuntimeError('Fixtures already seeded; inspect/read them instead of reseeding')
    else:
        saved={'state':'nominated','run_id':str(uuid4()),'database':state['active_db'],'objects':{}}
        with marker.open('x') as stream:json.dump(saved,stream,indent=2)
    assert saved['database']==state['active_db'],'Reconcile fixtures after a changed DB target'
    fixture=json.loads((local/'fixtures.json').read_text());observer=DockerObserver(config)
    validator=configuration(ROOT/'.local/operator/trust.json')
    snapshot=Catalog(ROOT/'.local/operator/catalog',validator,readonly=True).snapshot()
    document=observer.state(observer.read(),snapshot)
    installation=next(item['installation_id'] for item in document['state']['installations'] if item['plugin_id']=='org.example.notes')
    fixture['bindings']={key:next(b for b in document['state']['bindings'] if b['workspace_id']==workspace['public_id']
        and b['consumer_installation_id']==installation and b['alias']=='documents') for key,workspace in fixture['workspaces'].items()}
    for key,actor in [('A','alice'),('B','bob')]:
        client=r1_probe.Client(state,fixture,actor)
        saved['objects'].setdefault(key,[])
        for index in range(2):
            title=f'G5 lifecycle {key}/{index} {saved["run_id"]}'
            body=f'Private synthetic {key} data\nArabic: مرحبا\nPreserve identity, revision and author.'
            result=client.call('create',{'title':title,'body':body},workspace=key,key=f'g5-data-{saved["run_id"]}-{key}-{index}')
            if index==0:
                result=client.call('update',{'note_id':result['id'],'expected_revision':1,'title':title+' revision two'},
                    workspace=key,key=f'g5-data-update-{saved["run_id"]}-{key}-{index}')
            assert result['revision']==(2 if index==0 else 1)
            native=client.native('search_read',[[('public_id','=',result['id'])]],{'fields':['id','public_id','title','body','revision','workspace_id','author_id']},workspace=key)
            assert len(native)==1 and native[0]['workspace_id'][0]==fixture['workspaces'][key]['id']
            if index>=len(saved['objects'][key]):saved['objects'][key].append({'dto':result,'native':native[0]})
            else:assert saved['objects'][key][index]=={'dto':result,'native':native[0]}
            marker.write_text(json.dumps(saved,indent=2)+'\n')
        other='B' if key=='A' else 'A'
        if saved['objects'].get(other):
            client.call('get',{'note_id':saved['objects'][other][0]['dto']['id']},workspace=key,expect=404,code='NOT_FOUND')
        client.native('create',[{'name':'Denied G5 workspace attachment','res_model':'mp.example.note',
            'res_id':saved['objects'][key][0]['native']['id'],'datas':'c3ludGhldGlj','public':False}],workspace=key,model='ir.attachment',deny=True)
    saved['state']='completed';saved['completed_at']=datetime.now(timezone.utc).isoformat()
    marker.write_text(json.dumps(saved,indent=2)+'\n')
    output=ROOT/'docs/evidence/G5'/('lifecycle-data-'+saved['run_id']);output.mkdir()
    report={'result':'passed_subset','utc':saved['completed_at'],'database':state['active_db'],'objects':saved['objects'],
        'count':sum(len(rows) for rows in saved['objects'].values()),'scoped_gateway_and_native_readback':True,
        'workspace_attachments_denied':True,'notes_digest':data_digest(saved['objects']),
        'source_sha256':{Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}}
    (output/'business-fixtures.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'passed_subset','count':report['count'],'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
