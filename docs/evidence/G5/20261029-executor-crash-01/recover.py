"""Separate exact reviews: fresh-target restore, then explicitly resume traffic."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import files


def main():
    global OUTPUT
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare-restore','restore','verify-restore','prepare-resume','resume']);parser.add_argument('--run',choices=['01','02'],default='01');args=parser.parse_args()
    if args.run=='02':OUTPUT=OUTPUT/'attempt02'
    stem='executor-crash'+('02' if args.run=='02' else '')
    load=lambda p:json.loads(p.read_text(encoding='utf8'))
    marker=LOCAL/(stem+'.json');record=load(marker);op=record['operation_id'];target=LOCAL/'operator/target.json';base=load(OUTPUT/'configuration-before.json');current=load(target);state=load(LOCAL/'state.json');generation=base['generation']+2
    assert state['disposable'] and current['project']==base['project']=='mp-r0-r1lifef99acae9d906'
    trust=ROOT/state['operator_trust_config'];catalog_root=ROOT/state['operator_catalog'];store=OperatorStore(LOCAL/'operator/control')
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(trust)];command=prefix+['plugin','recover']
    options=['--store',str(store.root),'--deployment-config',str(target),'--catalog',str(catalog_root)]
    def phase(value,**extra):
        record.update(state=value,utc=datetime.now(timezone.utc).isoformat(),**extra);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    def write(name,value):
        with (OUTPUT/name).open('x',encoding='utf8') as f:f.write(json.dumps(value,indent=2)+'\n')
    def invoke(arguments):
        r=subprocess.run(arguments,cwd=ROOT,capture_output=True,timeout=600)
        if r.returncode:
            (LOCAL/('executor-crash-'+args.action+'.log')).write_bytes(r.stderr)
            raise RuntimeError('Recovery CLI failed: reconcile marker/journal/owned targets, never retry restore or reset a DB')
        return json.loads(r.stdout)
    if args.action=='prepare-restore':
        assert record['state']=='recovery_required_verified' and current==base
        envelope=invoke(command+['prepare-restore',op]+options);decision=envelope['decision']
        assert decision['configuration']==base and decision['restore_configuration']['image_id']==base['image_id']
        assert decision['restore_configuration']['generation']==generation and decision['keep_traffic_closed']
        assert decision['fresh_database']=='mp_disposable_r0_r1_restore_'+op.replace('-','')
        write('restore-review.json',envelope);write('restore-decision.json',decision);phase('restore_independently_reviewed',restore_hash=envelope['decision_hash'])
        print(json.dumps(dict(state=record['state'],operation_id=op,decision_hash=envelope['decision_hash'],fresh_database=decision['fresh_database'],generation=generation)));return
    if args.action in ('restore','verify-restore'):
        decision=load(OUTPUT/'restore-decision.json');assert data_digest(decision)==record['restore_hash']
        if args.action=='restore':
            assert record['state']=='restore_independently_reviewed' and current==base
            phase('restoring_reviewed_fresh_target');result=invoke(command+['restore',op,'--decision',str(OUTPUT/'restore-decision.json'),'--decision-hash',record['restore_hash'],'--noninteractive']+options)
            write('restore-result.json',result);assert result['state']=='restored_verified' and result['keep_traffic_closed'] and result['failed_database_retained'];phase('restored_needs_verification')
        else:
            assert record['state']=='restored_needs_verification' and load(OUTPUT/'restore-result.json')['state']=='restored_verified'
            assert store.status(op)['phase']=='restore_verified' and not store.status(op)['traffic_resumed']
            write('verification-reconciliation.json',dict(result='existing_completed_restore_only',reason='Optional private fixture database key absent; no restore retry',operation_id=op))
        restored=load(target);assert restored['generation']==generation and restored['image_id']==base['image_id'] and restored['worker_id']!=base['worker_id']
        assert restored['sites'][0]['database']==decision['fresh_database'] and restored['sites'][0]['site_id']==base['sites'][0]['site_id']
        state.update(phase='executor_crash_restored_traffic_closed',active_db=restored['sites'][0]['database'],generation=generation,image_id=restored['image_id'],worker_id=restored['worker_id'])
        state['databases']=list(dict.fromkeys(state['databases']+[state['active_db']]))
        (LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
        fixture=load(LOCAL/'fixtures.json');history=fixture.setdefault('database_history',[])
        if base['sites'][0]['database'] not in history:history.append(base['sites'][0]['database'])
        fixture['database']=state['active_db'];(LOCAL/'fixtures.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf8')
        reader=DockerObserver(restored);catalog=Catalog(catalog_root,configuration(trust),readonly=True).snapshot();observed=reader.state(reader.read(),catalog)['state']
        before=load(OUTPUT/'state-before.json');business=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));assert business==load(OUTPUT/'business-before.json') and schema==load(OUTPUT/'schema-before.json')
        assert observed['installations']==before['installations'] and observed['bindings']==before['bindings']
        expected=dict(before['release_lock'],generation=generation,created_at=restored['published_release']['created_at']);assert observed['release_lock']==expected
        old_files=load(OUTPUT/'files-before.json');now=files(reader);assert all(now[n]==h for n,h in old_files.items())
        failed=DockerObserver(base);assert json.loads(sql(failed,BUSINESS_SQL))==load(OUTPUT/'business-after-commit.json') and json.loads(sql(failed,SCHEMA))==load(OUTPUT/'schema-after-commit.json')
        old_secret=json.loads(sql(failed,"SELECT to_jsonb(md5(value)) FROM ir_config_parameter WHERE key='database.secret';"));new_secret=json.loads(sql(reader,"SELECT to_jsonb(md5(value)) FROM ir_config_parameter WHERE key='database.secret';"));assert old_secret and new_secret and old_secret!=new_secret
        edge=reader._container('edge',stopped=True);assert not load_docker(edge)['State']['Running']
        old_worker=load_docker(base['worker_id']);assert not old_worker['State']['Running'] and base['project']+'_runtime' not in old_worker['NetworkSettings']['Networks']
        assert store.status(op)['state']=='revoked' and store.status(op)['phase']=='restore_verified' and not store.status(op)['traffic_resumed']
        for name,value in [('configuration-restored',restored),('state-restored',observed),('business-restored',business),('schema-restored',schema),('files-restored',now)]:write(name+'.json',value)
        write('restored-invariants.json',dict(result='passed_restored_before_traffic',generation=generation,failed_database_retained=True,failed_database_unchanged=True,old_note_board_grant_binding_rows_exact=True,old_files_preserved=len(old_files),previous_plugin_versions_and_field_restored=True,session_secret_rotated=True,old_worker_stopped_disconnected=True,traffic_closed=True))
        phase('restored_verified_traffic_closed',active_database=state['active_db'],generation=generation);print(json.dumps(dict(state=record['state'],operation_id=op,generation=generation)));return
    if args.action=='prepare-resume':
        assert record['state']=='restored_verified_traffic_closed' and current['generation']==generation
        envelope=invoke(command+['prepare-resume',op]+options);write('resume-review.json',envelope);write('resume-decision.json',envelope['decision']);phase('resume_independently_reviewed',resume_hash=envelope['decision_hash'])
        print(json.dumps(dict(state=record['state'],operation_id=op,decision_hash=envelope['decision_hash'],generation=generation)));return
    assert record['state']=='resume_independently_reviewed' and current['generation']==generation
    phase('resuming_reviewed_restored_target');result=invoke(command+['resume',op,'--decision',str(OUTPUT/'resume-decision.json'),'--decision-hash',record['resume_hash'],'--noninteractive']+options)
    write('resume-result.json',result);assert result['state']=='restored_traffic_resumed' and result['original_plan_state']=='revoked'
    assert store.status(op)['state']=='revoked' and store.status(op)['phase']=='restore_traffic_resumed'
    state['phase']='executor_crash_restored_resumed';(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');phase('completed_verified')
    write('recovery-qualification.json',dict(result='passed_actual_process_crash_reconciliation_restore_resume' if (OUTPUT/'process-crash.json').exists() else 'recovered_launcher_harness_failure_not_OS_crash',operation_id=op,original_generation=base['generation'],planned_failed_generation=base['generation']+1,restored_generation=generation,fresh_database=state['active_db'],failed_database_retained=True,original_plan_revoked=True,limits=['Supported HTTP/assets/client fence and protected/source audit remain separate.','No concurrency, job/outbox adapter or clean-environment restore qualification.']))
    print(json.dumps(dict(state=record['state'],operation_id=op,generation=generation)))


def load_docker(name):return json.loads(subprocess.check_output(['docker','inspect',name]))[0]


if __name__=='__main__':main()
