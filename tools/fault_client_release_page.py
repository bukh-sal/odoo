"""Bounded missing-page fault in clone metadata; immutable package bytes stay fixed."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest
from qualify_client_release_clone import command


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['inject','restore']);args=parser.parse_args()
    private=ROOT/'.local/g5/client-release-clones';parent=private/'20261028-client-release-clone-01.json'
    clone=json.loads(parent.read_text(encoding='utf-8'));assert clone['experimental_not_approved_release']
    database=clone['database'];assert re.fullmatch(r'mp_disposable_r0_r1_client_[0-9a-f]{16}',database) and database!=clone['source_database']
    db=command(['docker','ps','--filter','label=com.docker.compose.project='+clone['source_project'],'--filter','label=com.docker.compose.service=db','--format','{{.ID}}']).decode().strip()
    assert re.fullmatch('[0-9a-f]+',db)
    def sql(text):return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',database],input=text.encode())
    current=json.loads(sql("SELECT manifest FROM mp_plugin_installation WHERE plugin_id='org.example.canvas' AND state='installed';"))
    marker=private/'20261028-client-release-clone-01-page-fault.json'
    if args.action=='inject':
        if marker.exists():raise ValueError('Fault already attempted; inspect it without replay')
        changed=copy.deepcopy(current);changed['ui']['pages'][0]['id']='g5_fault_missing_page'
        record={'state':'prepared','original':current,'changed':changed,'database':database};_write_new(marker,record)
        expected,value=current,changed
    else:
        record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='injected' and current==record['changed']
        expected,value=record['changed'],record['original']
    literal=lambda value:"'"+json.dumps(value).replace("'","''")+"'::jsonb"
    sql("SET standard_conforming_strings=on; UPDATE mp_plugin_installation SET manifest="+literal(value)+" WHERE plugin_id='org.example.canvas' AND manifest="+literal(expected)+";")
    assert json.loads(sql("SELECT manifest FROM mp_plugin_installation WHERE plugin_id='org.example.canvas';"))==value
    record['state']='injected' if args.action=='inject' else 'restored';marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'state':record['state'],'clone_only':True,'original_manifest_digest':data_digest(record['original']),'package_bytes_changed':False}))


if __name__=='__main__':main()
