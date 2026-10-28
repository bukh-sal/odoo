"""Read real Notes/API/native boundaries and restored asset bytes after G5 work."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from qualify_native_upgrade import sql
import r1,r1_probe
r1.r0.LOCAL=ROOT/'.local/g5'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or output.exists():raise ValueError('Fresh G5 verification directory required')
    local=r1.r0.LOCAL;operator=ROOT/'.local/operator';state=json.loads((local/'state.json').read_text())
    config=json.loads((operator/'targets/g5.json').read_text());assert state['active_db']==config['sites'][0]['database']
    fixture=json.loads((local/'fixtures.json').read_text());seeded=json.loads((local/'lifecycle-data.json').read_text())
    observer=DockerObserver(config);catalog=Catalog(operator/'catalog',configuration(operator/'trust.json'),readonly=True).snapshot()
    before=observer.state(observer.read(),catalog)['state']
    fixture['bindings']={}
    for key,row in fixture['workspaces'].items():
        consumer=next(item for item in before['installations'] if item['plugin_id']=='org.example.notes' and item['workspace_id']==row['public_id'])
        matches=[binding for binding in before['bindings'] if binding['consumer_installation_id']==consumer['installation_id']
            and binding['workspace_id']==row['public_id'] and binding['alias']=='documents']
        assert len(matches)==1 and matches[0]['contract_major']==1 and matches[0]['api_version']=='1.0'
        fixture['bindings'][key]=matches[0]
    alice=r1_probe.Client(state,fixture,'alice');bob=r1_probe.Client(state,fixture,'bob')
    for row in seeded['objects']['A']:
        assert alice.call('get',{'note_id':row['dto']['id']},workspace='A')==row['dto']
        assert alice.native('read',[[row['native']['id']],['id','public_id','title','body','revision','workspace_id','author_id']],workspace='A')==[row['native']]
    foreign=seeded['objects']['B'][0]
    alice.native('read',[[foreign['native']['id']],['title']],workspace='A',deny=True)
    alice.call('get',{'note_id':foreign['dto']['id']},workspace='B',expect=403,code='FORBIDDEN')
    bob.call('get',{'note_id':foreign['dto']['id']},workspace='B',expect=403,code='FORBIDDEN')
    assets=json.loads(sql(observer,"SELECT COALESCE(jsonb_agg(a),'[]'::jsonb) FROM (SELECT url,checksum,file_size FROM ir_attachment WHERE store_fname IS NOT NULL AND url LIKE '/web/assets/%' ORDER BY id LIMIT 1) a;"))
    assert len(assets)==1
    asset=assets[0];assert asset['url'].startswith('/web/assets/') and not asset['url'].startswith('//')
    with alice.http.open(urllib.request.Request(alice.base+asset['url']),timeout=30) as response:
        raw=response.read();assert response.status==200
    assert hashlib.sha1(raw).hexdigest()==asset['checksum'] and len(raw)==asset['file_size']
    after=observer.state(observer.read(),catalog)['state'];assert after==before
    report={'result':'passed_subset','utc':datetime.now(timezone.utc).isoformat(),'image_id':config['image_id'],
        'generation':config['generation'],'notes_read_gateway_and_native':2,'notes_exact_consumer_major1_bindings':True,'cross_workspace_native_denied':True,
        'suspended_B_denied':True,'revoked_B_principal_denied':True,'restored_asset':asset,
        'asset_http_bytes_match_filestore_checksum':True,'deployment_state_unchanged':True,'state_digest':data_digest(after),
        'source_sha256':{Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'limits':['Workspace attachments are deliberately excluded; this verifies a supported internal filestore asset read.']}
    output.mkdir();(output/'business-api-assets.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':'passed_subset','evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
