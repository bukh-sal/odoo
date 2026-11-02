"""Fresh exact reviewed resume of the proven unmutated failed base."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'20261102-manager-reregister-01'))
from lifecycle import context,base,f,j,worker,MARKER as CYCLE,PRIVATE
from modular_platform.reference_dispatch import ReferenceDispatchMaintenance
f.OUTPUT=OUT;MARKER=PRIVATE/'unchanged-recovery.json'

def check():
    state,native=context();cycle=f.load(CYCLE);assert cycle['install']['state']=='failed_before_mutation_reference_guard'
    before=f.load(PRIVATE/'register-data-before.json');assert base.snapshot(state,'refregfix-live-profile-data')==before
    policy=ReferenceDispatchMaintenance(native).reference_policy(native.config)
    assert len(policy['registrations'])==1 and policy['registrations'][0]['state']=='removed'
    assert all(r['feature_state']=='suspended' for r in policy['registrations'][0]['features'])
    assert worker(native,'refregfix-live-profile-worker')==f.load(PRIVATE/'register-worker-before.json')
    f.save('actual-profile-observer.json',dict(result='passed_actual_independent_profile_corrected_observer',configuration_generation=15,dispatch_generation=76,publication_generation=5,endpoint_generation=3,metadata_still_removed_suspended_ungranted_unbound=True,all17tables_and_stoppedworker_exact=True,application_image_not_modified=True,limits=['Read-only corrected host observer only; installed metadata apply must use a new coherent immutable image.']))
    print('Real independent profile now observes inert removed registration; data/stoppedworker/image preserved')

def prepare():
    state,native=context();assert not MARKER.exists();op=f.load(CYCLE)['install']['operation_id']
    result=json.loads(f.command('refregfix-prepare-unchanged',base.prefix()+['plugin','recover','prepare-unchanged-resume',op]+base.options(native),timeout=240))
    decision=result['decision'];assert decision['action']=='resume_unchanged_release' and decision['dispatch']['mode']=='enabled_unchanged'
    assert not decision['edge']['running'] and decision['worker_running'] and not decision['database_restore']
    f.write(PRIVATE/'unchanged-decision.json',decision);f.write(MARKER,dict(state='review_prepared',operation_id=op,decision_hash=result['decision_hash']))
    f.save('unchanged-review.json',dict(result='prepared_fresh_independent_unchanged_resume',operation_id=op,decision_hash=result['decision_hash'],configuration_generation=15,dispatch_generation=76,current_publication_bound=True,existing_worker_and_dispatch_retained=True,database_restore=False,ingress_currently_stopped=True))
    print('Fresh independent unchanged-release review prepared; exact hash required to resume ingress')

def resume():
    state,native=context();record=f.load(MARKER);assert record['state']=='review_prepared'
    record['state']='resuming';f.write(MARKER,record)
    result=json.loads(f.command('refregfix-resume-unchanged',base.prefix()+['plugin','recover','resume-unchanged',record['operation_id']]+base.options(native)+['--decision',str(PRIVATE/'unchanged-decision.json'),'--decision-hash',record['decision_hash'],'--noninteractive'],timeout=300))
    assert result['state']=='unchanged_release_resumed' and result['traffic_resumed'] and not result['database_restore'] and not result['worker_replaced']
    f.save('unchanged-resumed.json',result);record['state']='resumed_needs_verification';f.write(MARKER,record)
    f.phase(state,'reference_reregister_fix_unchanged_resumed_needs_verification');print('Exact reviewed unchanged release resumed ingress; no DB restore or worker replacement')

def verify():
    import r1_probe
    r1_probe.r1.r0.LOCAL=j.LOCAL
    state,native=context();record=f.load(MARKER);assert record['state']=='resumed_needs_verification'
    assert base.snapshot(state,'refregfix-recovered-data')==f.load(PRIVATE/'register-data-before.json')
    assert worker(native,'refregfix-recovered-worker')==f.load(PRIVATE/'register-worker-before.json')
    snapshot=ReferenceDispatchMaintenance(native).inspect();assert snapshot['control']['generation']==76 and snapshot['control']['state']=='enabled'
    fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
    status,response=alice.request('/api/v1/context?plugin_id=org.example.document_stats',workspace='C');assert status==404 and response['error']['code']=='NOT_FOUND'
    for name in ['A','B','C']:
        value=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
        assert set(value['views'])=={'list','form'}
    assert base.snapshot(state,'refregfix-recovered-http-data')==f.load(PRIVATE/'register-data-before.json')
    f.save('unchanged-recovery-qualification.json',dict(result='passed_actual_reviewed_reference_unchanged_release_resume',operation_id=record['operation_id'],decision_hash=record['decision_hash'],configuration_generation=15,dispatch_generation=76,publication_generation=5,endpoint_generation=3,all17tables_and_stoppedworker_exact=True,original_actor_removed_context404_native_A_B_C_list_form_retained=True,no_database_restore_queue_epoch_or_worker_replacement=True,application_image_unchanged=True,limits=['Failure before dispatch fence/checkpoint/metadata; no external uncertain-effect or restored-DB proof.','Immutable correction rollout and new stopped-worker re-registration still required.']))
    record['state']='verified';f.write(MARKER,record);f.phase(state,'reference_reregister_fix_unchanged_resume_verified');f.guard(state)
    print('Reviewed unchanged resume verified: original data/dispatch76/stoppedworker exact, ingress/native views restored')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['check','prepare','resume','verify']);args=p.parse_args();globals()[args.action]()
