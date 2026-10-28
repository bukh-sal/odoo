"""Once-only positive B feature fixture for browser ID08, with exact restore."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from modular import configuration
from qualify_client_release_clone import BUSINESS_SQL,command


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['arm','restore']);args=parser.parse_args()
    directory=ROOT/'docs/evidence/G5/20261028-client-release-two-tabs-01'
    marker=ROOT/'.local/g5/client-release-clones/20261028-client-release-two-tabs-01.json'
    clone=json.loads((marker.parent/'20261028-client-release-clone-01.json').read_text(encoding='utf-8'))
    assert clone['database']=='mp_disposable_r0_r1_client_d44f98595a294031' and clone['generation']==18
    target=json.loads((ROOT/'.local/operator/targets/g5.json').read_text(encoding='utf-8'));observer=DockerObserver(target)
    catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    assert data_digest(observer.state(observer.read(),catalog)['state'])==clone['source_state_digest']
    def sql(query):return command(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',clone['database']],input=query.encode())
    if args.action=='arm':
        assert not directory.exists() and not marker.exists()
        business=json.loads(sql(BUSINESS_SQL));assert data_digest(business)==clone['business_digest']
        record={'state':'arming','business':business,'database':clone['database'],'utc':datetime.now(timezone.utc).isoformat()}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');directory.mkdir();(directory/'browser').mkdir()
        sql("UPDATE mp_workspace_plugin SET availability='enabled' WHERE plugin_id='org.example.notes' AND workspace_id=2; UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=2;")
        record['state']='armed';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'result':'armed','notes':[{'workspace_id':n['workspace_id'],'title':n['title'],'public_id':n['public_id']} for n in business['notes']]}))
    else:
        record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='armed'
        for row in record['business']['features']:
            sql(f"UPDATE mp_workspace_plugin SET availability='{row['availability']}' WHERE id={row['id']};")
        sql('UPDATE mp_workspace SET policy_generation=policy_generation+1 WHERE id=2;')
        assert json.loads(sql(BUSINESS_SQL))==record['business']
        assert data_digest(observer.state(observer.read(),catalog)['state'])==clone['source_state_digest']
        record['state']='restored';record['utc']=datetime.now(timezone.utc).isoformat()
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'result':'restored','original_business_exact':True,'source_unchanged':True}))


if __name__=='__main__':main()
