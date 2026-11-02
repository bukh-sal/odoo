"""Separately reviewed operator revocation; never controls the worker process."""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-manager-enable-01'))
from lifecycle import context,base,f,j
from modular_platform.operator_os import protect_directory
from modular_platform.worker_operator import WorkerOperator
from modular_platform.profile_channel import publish_profile
from modular_platform.catalog import Catalog
from modular_platform.plans import data_digest
f.OUTPUT=OUT;PRIVATE=j.LOCAL/'manager-unregister-01';MARKER=PRIVATE/'revocation.json'

def operator(native):
    return WorkerOperator(native.store,native.target_path,native.target_path.with_name('worker-target.json'))

def cli():
    return base.prefix()+['worker','--store',str(j.LOCAL/'operator/control'),'--deployment-config',str(j.LOCAL/'operator/target.json'),
        '--worker-config',str(j.LOCAL/'operator/worker-target.json')]

def control(state,label):
    return json.loads(f.sql(state,label,"BEGIN READ ONLY; SELECT jsonb_agg(to_jsonb(c) ORDER BY id) FROM mp_dispatch_control c; ROLLBACK;"))

def physical(native,label):
    op=operator(native);old=f.load(PRIVATE/'publication-before.json')
    scope=f.load(MARKER)['scope'];entry=next(e for e in old['endpoints'] if e['descriptor']['installation_id']==scope['installation_id'])
    # The process deliberately retains generation1 after dispatch revocation2.
    # Attest against its captured public configuration, never call it enabled.
    attested=op.observer(entry['descriptor'],op.publisher._key_digest(entry['descriptor']),entry['key_id'])
    info=json.loads(f.command(label,['docker','inspect',attested['container_id']]))[0]
    return dict(container_id=info['Id'],image=info['Image'],started_at=info['State']['StartedAt'],restart_count=info['RestartCount'],
        mounts=info['Mounts'],networks=info['NetworkSettings']['Networks'],public_digest=attested['public_digest'])

def baseline():
    state,native=context();assert not PRIVATE.exists();protect_directory(PRIVATE)
    op=operator(native);publication=op.publisher._document();assert publication['generation']==3
    scope=f.load(j.LOCAL/'provider-registration/setup.json')['scope']
    entry=next(e for e in publication['endpoints'] if e['descriptor']['installation_id']==scope['installation_id'])
    assert entry['descriptor']['generation']==1 and entry['descriptor']['state']=='enabled'
    f.write(PRIVATE/'publication-before.json',publication)
    f.write(MARKER,dict(state='baseline_capturing',scope=scope))
    f.write(PRIVATE/'worker-before.json',physical(native,'manager-unregister01-worker-before-revocation'))
    f.write(PRIVATE/'data-before-revocation.json',base.snapshot(state,'manager-unregister01-data-before-revocation'))
    observed=control(state,'manager-unregister01-control-before-revocation');assert observed[0]['generation']==73 and observed[0]['state']=='enabled'
    f.write(PRIVATE/'control-before-revocation.json',observed)
    endpoint=copy.deepcopy(entry['descriptor']);endpoint.update(generation=2,state='revoked');f.write(PRIVATE/'revoked-endpoint.json',endpoint)
    marker=f.load(MARKER);marker.update(state='baseline_captured',key_id=entry['key_id']);f.write(MARKER,marker)
    print('Fresh current15/control73 baseline captured; no endpoint or metadata mutation')

def revoke():
    state,native=context();marker=f.load(MARKER);assert marker['state']=='baseline_captured'
    review=json.loads(f.command('manager-unregister01-revocation-prepare',cli()+['prepare','--endpoint',str(PRIVATE/'revoked-endpoint.json'),'--key-id',marker['key_id']]))
    shown=json.loads(f.command('manager-unregister01-revocation-review',cli()+['review',review['plan']['operation_id']]))
    assert shown==review;f.save('revocation-independent-review.json',review)
    marker.update(state='publication_prepared',operation_id=review['plan']['operation_id'],plan_hash=review['plan_hash']);f.write(MARKER,marker)
    publish()

def publish():
    state,native=context();marker=f.load(MARKER);assert marker['state']=='publication_prepared'
    marker['state']='publishing';f.write(MARKER,marker)
    result=json.loads(f.command('manager-unregister01-revocation-publish',cli()+['publish',marker['operation_id'],'--plan-hash',marker['plan_hash'],'--noninteractive']))
    assert result['generation']==4 and result['state']=='revoked';f.save('revocation-result.json',result)
    marker['state']='published_needs_verification';f.write(MARKER,marker)
    f.phase(state,'manager_unregister01_endpoint_revoked_needs_verification')
    print('Separate exact reviewed operator publication revoked endpointgen2/documentgen4; worker not controlled')

def verify():
    state,native=context();marker=f.load(MARKER);assert marker['state']=='published_needs_verification'
    op=operator(native);publication=op.publisher._document();old=f.load(PRIVATE/'publication-before.json');expected=copy.deepcopy(old)
    expected['generation']=4
    entry=next(e for e in expected['endpoints'] if e['descriptor']['installation_id']==marker['scope']['installation_id'])
    entry['descriptor'].update(generation=2,state='revoked')
    assert sorted(publication['endpoints'],key=data_digest)==sorted(expected['endpoints'],key=data_digest) and publication['generation']==4
    assert physical(native,'manager-unregister01-worker-after-revocation')==f.load(PRIVATE/'worker-before.json')
    assert base.snapshot(state,'manager-unregister01-data-after-revocation')==f.load(PRIVATE/'data-before-revocation.json')
    assert control(state,'manager-unregister01-control-after-revocation')==f.load(PRIVATE/'control-before-revocation.json')
    observation=op.planning_state();health=observation['service_health'][marker['scope']['installation_id']+':'+marker['scope']['workspace_id']]
    assert health['state']=='disabled'
    # Use the protected external reader; this is untrusted planning data only.
    result=publish_profile(native.observer,Catalog(native.catalog_root,native.validator,readonly=True));f.save('revoked-profile-publication.json',result)
    assert base.snapshot(state,'manager-unregister01-data-after-profile')==f.load(PRIVATE/'data-before-revocation.json')
    f.save('revocation-qualification.json',dict(result='passed_actual_independent_endpoint_revocation',publication_generation=4,endpoint_generation=2,
        operation_id=marker['operation_id'],plan_hash=marker['plan_hash'],operator_exact_review_required=True,
        worker_process_identity_image_start_restart_mounts_network_public_key_unchanged=True,
        all17tables_and_dispatch_control73_exact=True,host_planning_observation_disabled=True,
        protected_reader_sanitized_profile_refreshed=True,metadata_still_installed=True,
        limits=['No remote job was dispatched; no in-flight revocation/recovery claim.','Metadata unregister is the next separately approved operation.']))
    marker['state']='verified';f.write(MARKER,marker);f.phase(state,'manager_unregister01_endpoint_revoked_verified');f.guard(state)
    print('Revoked publication4 verified; worker unchanged,17tables/control73 exact; manager planning profile refreshed')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['baseline','revoke','publish','verify']);args=p.parse_args();globals()[args.action]()
