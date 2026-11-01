"""Actual protected OS publication -> controlled read-only child -> retirement."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.operator_store import OperatorStore
from modular_platform.native_executor import NativeExecutor
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
from modular_platform.operator_os import protect_directory
from modular_platform.deployment import _run
from modular import configuration

TABLES=['mp_plugin_installation','mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential',
    'mp_workspace','mp_membership','mp_principal','mp_audit_event','ir_config_parameter','ir_module_module',
    'mp_job','mp_dispatch_control','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption',
    'mp_event_consumer_state','mp_example_note']

def main():
    local=ROOT/'.local/g6-events';marker=local/'reference-host-inspect-01.json'
    if marker.exists():raise RuntimeError('Inspect the existing read-only child; never duplicate it')
    state=json.loads((local/'state.json').read_text());target=local/'operator/target.json'
    protected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in state['protected_configurations']}
    assert protected==state['protected_configurations']
    target_hash=hashlib.sha256(target.read_bytes()).hexdigest()
    store=OperatorStore(local/'operator/control')
    native=NativeExecutor(store,target,local/'operator/catalog',configuration(local/'operator/trust.json'))
    helper=ReferenceDispatchMaintenance(native)
    def snapshot():
        parts=["'"+table+"',(SELECT jsonb_build_array(count(*),encode(sha256(convert_to(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY id)::text,'[]'),'UTF8')),'hex')) FROM "+table+' t)' for table in TABLES]
        query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT jsonb_build_object("+','.join(parts)+"); ROLLBACK;"
        return json.loads(_run(['docker','exec','-i',native.observer._container('db'),'psql','-X','-qAt','-U','postgres',
            '-d',state['active_db'],'-v','ON_ERROR_STOP=1'],input=query.encode()))
    before=snapshot();marker.write_text(json.dumps(dict(state='running'))+'\n')
    result=helper.inspect();helper.require_profile(result)
    assert result['external_installations']==0 and not helper.policies[result['reference_policy_digest']]['registrations']
    record_paths=list((store.root/'dispatch-inspections').glob('*/observe.json'))
    records=[(p,json.loads(p.read_text())) for p in record_paths if json.loads(p.read_text())['result']==result]
    assert len(records)==1
    path,record=records[0];child=record['child']
    identity=json.loads(_run(['docker','inspect','--format','{{json .Image}}',child]))
    terminal=json.loads(_run(['docker','inspect','--format','{{json .State}}',child]))
    assert identity==state['image_id'] and not terminal['Running'] and terminal['ExitCode']==0
    assert snapshot()==before
    assert hashlib.sha256(target.read_bytes()).hexdigest()==target_hash
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in protected.items())
    retired=protect_directory(ROOT/'.local/retired-docker-20261101/reference-host-inspect')
    (retired/(child+'.json')).write_text(json.dumps(dict(child=child,image=identity,terminal=terminal,private_record=str(path)),indent=2)+'\n')
    _run(['docker','rm',child])
    assert not _run(['docker','ps','--all','--filter','name='+child,'--format','{{.ID}}']).strip()
    report=dict(result='passed_real_readonly_reference_child',utc=datetime.now(timezone.utc).isoformat(),
        image=identity,profile=result['profile'],reference_policy_digest=result['reference_policy_digest'],
        external_registrations=0,current_protected_publication=True,actual_docker_child=True,child_exit_code=0,
        child_removed=True,new_images=0,new_volumes=0,nineteen_table_rows_preserved=True,protected_configurations_preserved=True,
        limits=['Current publication is revoked generation2 and database has no external registration.',
            'Read-only inspection only; no lifecycle approval, metadata commit, remote runtime or recovery qualification.'])
    (OUT/'host-inspect.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    marker.write_text(json.dumps(dict(state='completed',**report),indent=2)+'\n',encoding='utf8')
    print(json.dumps(report))

if __name__=='__main__':main()
