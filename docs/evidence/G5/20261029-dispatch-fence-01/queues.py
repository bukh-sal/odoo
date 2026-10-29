"""Synthetic effect receipts/queues; explicit fixture-only reconciliation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-dispatch'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import _write_new
from lifecycle_data_probe import sql

TABLES="SELECT jsonb_build_array(to_regclass('public.mp_job'),to_regclass('public.mp_outbox'));"


def context():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));config=load(LOCAL/'operator/target.json');state=load(LOCAL/'state.json')
    assert state['disposable'] and config['project']=='mp-r0-r1dispefb95a06d78f'
    return config,DockerObserver(config)


def receipts():
    root=LOCAL/'operator/fixture-effects';protect_directory(root);return root


def seed(case):
    assert case in ('failed','restored','late');config,reader=context();record_path=LOCAL/('queue-'+case+'.json');assert not record_path.exists()
    assert json.loads(sql(reader,TABLES))==[None,None]
    event=str(uuid4());fixture=str(uuid4());result=hashlib.sha256(('synthetic-external-completion:'+event).encode()).hexdigest();receipt=receipts()/(event+'.json')
    # A real durable local file effect outside the restored database. No network,
    # real delivery or G6 job adapter is involved in this bounded fixture.
    _write_new(receipt,dict(effect_id=event,external_writes=1,result_sha256=result))
    record=dict(state='creating',case=case,database=config['sites'][0]['database'],fixture_id=fixture,effect_id=event,result_sha256=result,external_receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest());_write_new(record_path,record)
    statement='BEGIN; '
    for table in ['mp_job','mp_outbox']:
        statement+="CREATE TABLE public."+table+" (fixture_id uuid NOT NULL,effect_id uuid PRIMARY KEY,state text NOT NULL,result_sha256 text NOT NULL); ALTER TABLE public."+table+" OWNER TO modular; INSERT INTO public."+table+" VALUES ('"+fixture+"','"+event+"','pending','"+result+"'); "
    sql(reader,statement+'COMMIT;');record['state']='pending_with_external_completion';record_path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    (OUTPUT/('queue-'+case+'-pending.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');return record


def quarantine(case):
    assert case in ('failed','restored','late');config,reader=context();path=LOCAL/('queue-'+case+'.json');record=json.loads(path.read_text(encoding='utf8'))
    assert record['state']=='pending_with_external_completion' and record['database']==config['sites'][0]['database']
    receipt=receipts()/(record['effect_id']+'.json');assert hashlib.sha256(receipt.read_bytes()).hexdigest()==record['external_receipt_sha256']
    rows=[]
    for table in ['mp_job','mp_outbox']:
        value=json.loads(sql(reader,'SELECT jsonb_agg(to_jsonb(t)) FROM public.'+table+' t;'))
        assert value==[dict(fixture_id=record['fixture_id'],effect_id=record['effect_id'],state='pending',result_sha256=record['result_sha256'])];rows.append(dict(table=table,rows=value))
    schema='mp_fixture_reconciled_'+case
    # Retain every synthetic row in an explicitly named inert namespace after
    # checking its external completion receipt. This is a test resolution, not
    # a shipped generic queue reconciler or permission to discard unknown work.
    statement='BEGIN; CREATE SCHEMA '+schema+' AUTHORIZATION modular; '
    for table in ['mp_job','mp_outbox']:statement+='ALTER TABLE public.'+table+' SET SCHEMA '+schema+"; UPDATE "+schema+'.'+table+" SET state='reconciled_completed'; "
    sql(reader,statement+'COMMIT;');assert json.loads(sql(reader,TABLES))==[None,None]
    assert hashlib.sha256(receipt.read_bytes()).hexdigest()==record['external_receipt_sha256']
    record.update(state='explicit_fixture_reconciliation_retained',retained_schema=schema);path.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    (OUTPUT/('queue-'+case+'-reconciliation.json')).write_text(json.dumps(dict(result='fixture_rows_retained_and_external_completion_verified',record=record,original_rows=rows,external_effect_repeated=False,production_reconciler_implemented=False),indent=2)+'\n',encoding='utf8')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['seed','quarantine']);parser.add_argument('case',choices=['failed','restored','late']);args=parser.parse_args()
    print(json.dumps(seed(args.case) if args.action=='seed' else quarantine(args.case)))
