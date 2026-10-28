"""One explicitly experimental epoch change in a recorded disposable clone."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest
from qualify_client_release_clone import BUSINESS_SQL,command


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--clone-record',type=Path,required=True)
    parser.add_argument('--expected-generation',type=int,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    marker=args.clone_record.resolve();private=ROOT/'.local/g5/client-release-clones'
    if not marker.is_relative_to(private):raise ValueError('Recorded project clone only')
    record=json.loads(marker.read_text(encoding='utf-8'));database=record['database'];image=record['image_id']
    assert record['experimental_not_approved_release'] is True and record['state'] in ('http_qualified','browser_qualifying')
    assert re.fullmatch(r'mp_disposable_r0_r1_client_[0-9a-f]{16}',database) and database!=record['source_database']
    assert command(['docker','inspect',record['app'],'--format','{{.Image}}']).decode().strip()==image
    target=json.loads((ROOT/'.local/operator/targets/g5.json').read_text(encoding='utf-8'))
    assert target['project']==record['source_project'] and target['sites'][0]['database']!=database
    db=command(['docker','ps','--filter','label=com.docker.compose.project='+target['project'],'--filter','label=com.docker.compose.service=db','--format','{{.ID}}']).decode().strip()
    assert re.fullmatch('[0-9a-f]+',db)
    output=args.output.resolve();assert output.is_relative_to(ROOT/'docs/evidence/G5') and not output.exists()
    attempt=private/(marker.stem+'-epoch-'+str(args.expected_generation+1)+'.json')
    if attempt.exists():raise ValueError('Epoch attempt already exists; reconcile, never replay')
    def sql(statement,name=database):
        return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',name],input=statement.encode())
    params="SELECT jsonb_object_agg(key,value) FROM ir_config_parameter WHERE key IN ('mp.release_generation','mp.release_digest','mp.active_inventory_digest');"
    before=json.loads(sql(params));assert before['mp.release_generation']==str(args.expected_generation)
    assert before['mp.active_inventory_digest']==record['inventory_digest']
    business=json.loads(sql(BUSINESS_SQL));source=json.loads(sql(params,record['source_database']))
    generation=args.expected_generation+1;digest=data_digest({'experimental_clone_epoch':database,'generation':generation,'image_id':image})
    operation={'state':'prepared','database':database,'previous':before,'generation':generation,'release_digest':digest,'business_digest':data_digest(business),'experimental_only':True}
    output.mkdir(parents=True);_write_new(attempt,operation)
    sql("BEGIN; SELECT value FROM ir_config_parameter WHERE key='mp.release_generation' FOR UPDATE; DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM ir_config_parameter WHERE key='mp.release_generation' AND value='"+str(args.expected_generation)+"') THEN RAISE EXCEPTION 'Clone epoch changed'; END IF; END $$; UPDATE ir_config_parameter SET value=CASE key WHEN 'mp.release_generation' THEN '"+str(generation)+"' ELSE '"+digest+"' END WHERE key IN ('mp.release_generation','mp.release_digest'); COMMIT;")
    assert json.loads(sql(BUSINESS_SQL))==business and json.loads(sql(params,record['source_database']))==source
    after=json.loads(sql(params));assert after['mp.release_generation']==str(generation)
    operation.update(state='completed',after=after,utc=datetime.now(timezone.utc).isoformat(),source_publication_unchanged=True,business_unchanged=True)
    attempt.write_text(json.dumps(operation,indent=2)+'\n',encoding='utf-8')
    record.update(state='browser_qualifying',generation=generation,release_digest=digest)
    marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (output/'experimental-epoch.json').write_text(json.dumps(operation,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':'completed','clone_generation':generation,'business_unchanged':True,'operated_source_unchanged':True}))


if __name__=='__main__':main()
