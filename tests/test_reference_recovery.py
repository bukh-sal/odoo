"""Known reference recovery epochs and closed-traffic orchestration boundaries.

Pure source checks; Docker, backup/restore and OS publication IO are substituted.
They do not qualify an installed metadata recovery operation.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'))
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.reference_recovery import ReferenceRecoveryDispatch,reference_needed
from modular_platform.restore_executor import recovery_configuration
import test_restore_dispatch as legacy

OP='00000000-0000-4000-8000-000000000500'
PROFILE='r1-reference-stateless-dispatch-v1'


def fixture():
    base=dict(generation=8,created_at='2026-11-01T00:00:00Z',core_inventory_digest='sha256:'+'a'*64,
        plugins=[dict(runtime='external_service',plugin_id='org.example.document_stats',version='0.1.0')])
    target=dict(copy.deepcopy(base),generation=9,created_at='2026-11-01T00:01:00Z')
    config=dict(project='mp-disposable-reference-test',deployment_id='deployment',sites=[dict(site_id='site',database='mp_disposable_r0_r1_source')],
        image_id='sha256:'+'b'*64,generation=8,release_created_at=base['created_at'],published_release=base)
    bundle=dict(plan_hash='sha256:'+'c'*64,plan=dict(operation_id=OP,created_at=target['created_at'],
        base_release_digest=data_digest(base),target_release_digest=data_digest(target),artifacts=[dict(runtime='external_service')]),
        operation_lock=dict(release=target))
    manifest=dict(operation_id=OP,plan_hash=bundle['plan_hash'],configuration=config,
        previous_release=dict(release_lock=base),dispatch_profile=dict(profile=PROFILE))
    native=Mock();native.config=config;native.target_path=Path('target.json')
    return native,bundle,manifest


def policy(publication='old'):
    return dict(profile='r1-reference-stateless-v1',site_id='site',runtime_image='fixed-image',
        publication_digest=data_digest(publication),registrations=[])


def snapshot(value,**changes):
    result=dict(profile=PROFILE,schema_digest='schema',external_installations=len(value['registrations']),
        active_credentials=0,api_keys=0,uncertain_jobs=0,control=dict(state='paused',generation=9),
        release_digest='release',reference_policy_digest=data_digest(value),tables={'jobs':{'rows':0}})
    result.update(changes);result['state_digest']=data_digest(result)
    return result


class ReferenceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.native,self.bundle,self.manifest=fixture()
        self.helper=ReferenceRecoveryDispatch(self.native,self.bundle,self.manifest)

    def metadata(self,lock):
        return dict(release_digest=data_digest(lock),release_generation=str(lock['generation']),active_inventory_digest=lock['core_inventory_digest'])

    def test_profile_detection_includes_failed_first_registration_and_null_native_checkpoint(self):
        self.assertTrue(reference_needed(self.native,self.bundle,self.manifest))
        self.native.config={'published_release':{'plugins':[]}}
        b=copy.deepcopy(self.bundle);b['operation_lock']['release']['plugins']=[]
        m=copy.deepcopy(self.manifest);m['configuration']=self.native.config;m['dispatch_profile']=None
        self.assertTrue(reference_needed(self.native,b,m))
        b['plan']['artifacts']=[]
        self.assertFalse(reference_needed(self.native,b,m))

    def test_wrong_checkpoint_or_approved_release_refused(self):
        for field in ['operation_id','plan_hash']:
            m=copy.deepcopy(self.manifest);m[field]='wrong'
            with self.subTest(field=field),self.assertRaises(OperatorError):ReferenceRecoveryDispatch(self.native,self.bundle,m)
        b=copy.deepcopy(self.bundle);b['operation_lock']['release']['generation']+=1
        with self.assertRaises(OperatorError):ReferenceRecoveryDispatch(self.native,b,self.manifest)

    def test_source_accepts_only_known_checkpoint_or_exact_approved_target(self):
        h=ReferenceRecoveryDispatch(self.native,self.bundle,self.manifest,purpose='source_inspection')
        for lock in [h.base,h.target]:self.assertEqual(h._metadata_release(self.native.config,self.metadata(lock)),lock)
        unknown=dict(h.target,generation=90)
        with self.assertRaisesRegex(OperatorError,'neither checkpoint'):h._metadata_release(self.native.config,self.metadata(unknown))
        with self.assertRaisesRegex(OperatorError,'read-only'):h.run('enable',OP,Path('unused'))

    def test_known_release_with_wrong_epoch_or_inventory_refused(self):
        h=ReferenceRecoveryDispatch(self.native,self.bundle,self.manifest,purpose='source_inspection')
        for key,value in [('release_generation','999'),('active_inventory_digest','unknown')]:
            m=self.metadata(h.base);m[key]=value
            with self.subTest(key=key),self.assertRaises(OperatorError):h._metadata_release(self.native.config,m)

    def restored(self):
        config,lock=recovery_configuration(self.native.config,self.manifest,self.bundle)
        config['sites'][0]['database']=self.helper.fresh_database
        return config,lock

    def test_exact_checkpoint_derived_fresh_epoch_accepted(self):
        config,lock=self.restored()
        self.assertEqual(self.helper._metadata_release(config,self.metadata(lock)),lock)
        self.assertGreater(lock['generation'],self.helper.target['generation'])

    def test_mutated_fresh_epoch_database_or_native_pins_refused(self):
        for change in ['database','generation','created_at','plugins','core_inventory_digest']:
            config,lock=self.restored()
            if change=='database':config['sites'][0]['database']='mp_disposable_r0_r1_unreviewed'
            else:
                lock[change]={'generation':8,'created_at':'another-time','plugins':[],'core_inventory_digest':'wrong'}[change]
                config['published_release']=lock
            with self.subTest(change=change),self.assertRaises(OperatorError):self.helper._metadata_release(config,self.metadata(lock))

    def test_restored_database_tag_must_equal_reviewed_configuration(self):
        config,lock=self.restored()
        with self.assertRaisesRegex(OperatorError,'publication differs'):self.helper._metadata_release(config,self.metadata(self.helper.base))

    def test_scope_allows_only_same_deployment_site_and_exact_fresh_database(self):
        config,_=self.restored();self.assertTrue(self.helper._matches_target(self.native.config,config))
        for key in ['project','deployment_id','site_id','database']:
            changed=copy.deepcopy(config)
            if key in ['project','deployment_id']:changed[key]='different'
            else:changed['sites'][0][key]='different'
            with self.subTest(key=key):self.assertFalse(self.helper._matches_target(self.native.config,changed))

    def compare(self,old,new,**changes):
        before=snapshot(old);after=snapshot(new,**changes)
        self.helper.policies[data_digest(new)]=new
        return self.helper.same_restored_dispatch(after,before,old)

    def test_new_review_may_bind_current_publication_without_restoring_old_authority(self):
        self.assertTrue(self.compare(policy(),policy('revoked-current-generation')))

    def test_policy_scope_image_and_queue_changes_cannot_be_hidden_as_publication_update(self):
        for key,value in [('runtime_image','changed'),('site_id','other'),('registrations',[{'state':'installed'}])]:
            changed=dict(policy('new'),**{key:value})
            with self.subTest(key=key):self.assertFalse(self.compare(policy(),changed))
        self.assertFalse(self.compare(policy(),policy('new'),tables={'jobs':{'rows':1}}))
        self.assertFalse(self.compare(policy(),policy('new'),release_digest='changed'))

    def test_bad_previous_hash_or_current_uncertainty_refused(self):
        old=policy();new=policy('new');self.helper.policies[data_digest(new)]=new
        before=snapshot(old);before['state_digest']='wrong'
        self.assertFalse(self.helper.same_restored_dispatch(snapshot(new),before,old))
        with self.assertRaises(OperatorError):self.helper.same_restored_dispatch(snapshot(new,uncertain_jobs=1),snapshot(old),old)

    def test_checkpoint_comparison_relaxes_only_outer_epoch_and_current_publication(self):
        old=policy();new=policy('new');self.helper.policies[data_digest(new)]=new
        self.assertTrue(self.helper.same_restored_dispatch(snapshot(new,release_digest='fresh'),snapshot(old),old,checkpoint=True))
        self.assertFalse(self.helper.same_restored_dispatch(snapshot(new,release_digest='fresh',control={'state':'paused','generation':99}),snapshot(old),old,checkpoint=True))


class ReferenceResumeTests(unittest.TestCase):
    def setUp(self):
        self.base=legacy.RestoreDispatchTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        b=self.base;b.effects.update(job_table=True,outbox_table=True);b.authority['has_dispatch_tables']=True
        n,bundle,manifest=fixture();self.helper=ReferenceRecoveryDispatch(n,bundle,manifest)
        self.current=policy('current-revoked')
        old=policy();result_path=b.root/'recoveries'/b.op/'result.json';result=json.loads(result_path.read_text())
        result.update(dispatch=snapshot(old),reference_policy=old);result_path.write_text(json.dumps(result))
        self.helper.inspect_current=Mock(side_effect=self.observe)
        self.helper.run=Mock(side_effect=lambda *args,**kwargs:b.timeline.append('enable'))
        b.recovery._dispatch_helper=Mock(return_value=self.helper)
        b.recovery._recovery_observer=Mock(return_value=b.native.observer)

    def observe(self,**kwargs):
        self.helper.policies[data_digest(self.current)]=copy.deepcopy(self.current)
        return snapshot(self.current)

    def test_reference_resume_binds_current_publication_and_fences_before_queue_enable(self):
        b=self.base;decision=b.decision();decision['review']['review_id']='00000000-0000-4000-8000-000000000901'
        self.assertEqual(decision['recovery_profile'],PROFILE)
        b.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(b.timeline,['journal','enable','start-edge'])
        self.assertEqual(self.helper.run.call_args.kwargs['expected_digest'],snapshot(self.current)['state_digest'])

    def test_publication_change_after_review_requires_fresh_review_before_enable(self):
        b=self.base;decision=b.decision();b.readiness_change=lambda:self.current.update(publication_digest=data_digest('later-revocation'))
        with self.assertRaisesRegex(OperatorError,'changed before traffic'):b.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(b.timeline,[]);self.helper.run.assert_not_called()

    def test_metadata_change_since_verified_result_denies_resume(self):
        self.current['runtime_image']='different'
        with self.assertRaisesRegex(OperatorError,'queues changed'):self.base.recovery._resume_state(self.base.op)
        self.assertEqual(self.base.timeline,[])


if __name__=='__main__':unittest.main()
