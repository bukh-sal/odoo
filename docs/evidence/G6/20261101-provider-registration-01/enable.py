"""Actual reference metadata enable before native connector selection."""
import copy,json,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from register import ROOT,OUT,j,f,PRIVATE,MARKER,REGISTRATION,context,snapshot,schema,worker,command
from modular_platform.catalog import Catalog

state,native=context();assert f.load(REGISTRATION)['state']=='verified' and native.config['generation']==12
marker_path=PRIVATE/'enable.json';assert not marker_path.exists()
setup=f.load(MARKER);scope=setup['scope']
nomination=dict(operation_type='enable',targets=[dict(**scope,plugin_id='org.example.document_stats',action='enable')])
f.save('enable-nomination.json',nomination)
prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
options=['--store',str(native.store.root),'--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
bundle=json.loads(command('plan-enable',prefix+['plugin','plan-external','--input',str(OUT/'enable-nomination.json')]+options))
native._runtime_preflight(bundle);f.save('enable-bundle.json',bundle)
assert bundle['operation_lock']['release']==native.config['published_release'] and not bundle['plan']['permission_changes']
before=snapshot(state,'provider-enable-before');f.write(PRIVATE/'enable-data-before.json',before)
identity=worker(native,'worker-before-enable');f.write(PRIVATE/'enable-worker-before.json',identity)
marker=dict(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);f.write(marker_path,marker)
ops=prefix+['operations','--store',str(native.store.root)];validation=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)]
command('register-enable-operation',ops+['register','--bundle',str(OUT/'enable-bundle.json')]+validation)
f.save('enable-independent-review.json',native.store.review(marker['operation_id'],native._validate()))
command('approve-enable',ops+['approve',marker['operation_id'],'--plan-hash',marker['plan_hash'],'--noninteractive','--ack-trust']+validation)
marker['state']='applying';f.write(marker_path,marker);f.phase(state,'provider_enable_applying')
completed=json.loads(command('apply-enable',prefix+['plugin','apply',marker['operation_id'],'--store',str(native.store.root)]+validation,timeout=600))
assert completed['state']=='completed';f.save('enable-completed.json',completed)
marker['state']='completed_needs_verification';f.write(marker_path,marker)
state,native=context();after=snapshot(state,'provider-enable-after')
assert native.config['generation']==12 and native.config['published_release']==bundle['operation_lock']['release']
assert worker(native,'worker-after-enable')==identity
assert schema(state,'provider-enable-schema-after')==f.load(PRIVATE/'schema-before.json')['digest']
module_rows=json.loads(f.sql(state,'provider-enable-native-modules',"BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(m) ORDER BY id) FROM ir_module_module m; ROLLBACK;"))
assert module_rows==f.load(PRIVATE/'native-modules-before.json')
stage=native.store.root/'stages'/marker['operation_id'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
assert ready['control']['generation']==57 and enabled['after']['control']['generation']==58 and ready['external_installations']==1
installation=next(r for r in before['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
workspace=next(r for r in before['mp_workspace'] if r['public_id']==scope['workspace_id'])
cutoff=datetime.fromisoformat(bundle['plan']['created_at'].replace('Z','+00:00'));updated=0
for table in before:
    expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
    if table=='mp_workspace_plugin':
        old=next(r for r in expected if r['installation_id']==installation['id'] and r['workspace_id']==workspace['id'])
        current=next(r for r in actual if r['id']==old['id'])
        assert old['availability']=='suspended' and current['availability']=='enabled'
        stamp=datetime.fromisoformat(current['write_date']).replace(tzinfo=timezone.utc);assert cutoff<=stamp<=datetime.now(timezone.utc)
        old.update(availability='enabled',write_date=current['write_date'])
    elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=1
    elif table=='mp_job':
        byid={r['public_id']:r for r in actual}
        for old in expected:
            current=byid[old['public_id']];changed={k for k in old if old[k]!=current[k]}
            assert changed<={'claim_generation','dispatch_generation'}
            if changed:
                assert current['claim_generation']==old['claim_generation']+1 and current['dispatch_generation']==57
                old.update(claim_generation=current['claim_generation'],dispatch_generation=57);updated+=1
    assert expected==actual,table+' changed outside exact feature/policy/epoch effects'
observation=native.observer.read();current=native.observer.state(observation,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
provider=next(i for i in current['installations'] if i['installation_id']==scope['installation_id']);assert provider['state']=='installed' and provider['feature_state']=='enabled'
assert current['service_health'][scope['installation_id']+':'+scope['workspace_id']]['state']=='healthy'
assert f.load(stage/'metadata.log')==dict(metadata_published=True,operation_id=marker['operation_id'],native_maintenance=False,runtime_control=False)
f.save('enable-qualification.json',dict(result='passed_actual_metadata_enable',operation_id=marker['operation_id'],image=native.config['image_id'],
    configuration_generation=12,dispatch_generation=58,release_unchanged=True,approved_provider_healthy_and_enabled=True,
    worker_identity_image_start_restart_mounts_network_key_and_publication_exact=True,native_modules_and_schema_exact=True,
    all_business_authority_event_binding_grant_rows_exact=True,old_job_outcomes_inputs_attempts_exact=True,jobs_epoch_updated=updated,
    limits=['No connector, remote Note computation, outage/revocation/upgrade/unregister or external recovery qualification yet.']))
marker['state']='verified';f.write(marker_path,marker);f.phase(state,'provider_enabled_verified');f.guard(state)
print('Actual provider enable verified; independent worker unchanged; original native/business/queue data preserved')
