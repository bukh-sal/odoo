"""Real journal retirement and fail-closed unchanged-worker recovery boundary."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
from modular_platform.operator_os import OperatorError,OperationLocks
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import prepare_plan,release_lock,data_digest
from modular_platform.recovery_reviews import RecoveryReviews
from modular_platform.unchanged_recovery import validate_failed_base,validate_base_worker
from test_plans import base_state,solution,plugin,PROVENANCE,STAMP,target,ident

DIGEST='sha256:'+'a'*64


class JournalTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'control';self.state=base_state()
        self.store=OperatorStore.initialize(self.root,{self.state['deployment_id']:self.state['site_ids']})
        resolved=solution([plugin('a')]);lock=release_lock(resolved,PROVENANCE,generation=2,created_at=STAMP)
        self.bundle=prepare_plan(self.state,lock,resolved,[target()],operation_id=ident(500),created_at=STAMP)
        self.operation=self.store.register(self.bundle,self.revalidate)
        self.store.approve(self.operation,exact_hash=self.bundle['plan_hash'],acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=True),revalidate=self.revalidate)

    def revalidate(self,bundle):return copy.deepcopy(self.state)

    def locks(self):return OperationLocks(self.root/'locks',self.state['deployment_id'],self.state['site_ids'])

    def drain(self,locks):
        self.store.reserve(self.operation,locks,self.revalidate)
        for phase in ['staged','maintenance','drained']:self.store.advance(self.operation,locks,phase)
        self.store.advance(self.operation,locks,'checkpointed',backup_id='retained-test-backup')

    def test_resume_retires_authority_preserves_failure_and_fences_original_plan(self):
        with self.locks() as locks:
            self.drain(locks);self.store.fail(self.operation,locks,code='MUTATION_FAILED')
        before=self.store.bundle(self.operation)
        with self.locks() as locks:
            for phase in ['unchanged_resume_started','unchanged_release_ready','unchanged_traffic_resumed']:
                self.store.record_unchanged_resume(self.operation,locks,decision_hash=DIGEST,phase=phase)
        status=self.store.status(self.operation)
        self.assertEqual(status['state'],'failed_before_mutation');self.assertFalse(status['mutation_started']);self.assertTrue(status['traffic_resumed'])
        self.assertEqual(self.store.bundle(self.operation),before)
        with self.locks() as locks,self.assertRaisesRegex(OperatorError,'revoked'):
            self.store.reserve(self.operation,locks,self.revalidate)
        with self.assertRaisesRegex(OperatorError,'revocation is final'):
            self.store.approve(self.operation,exact_hash=self.bundle['plan_hash'],acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=True),revalidate=self.revalidate)

    def test_possible_native_mutation_cannot_use_unchanged_resume(self):
        with self.locks() as locks:
            self.drain(locks);self.store.before_mutation(self.operation,locks,self.revalidate);self.store.fail(self.operation,locks,code='MUTATION_FAILED')
            with self.assertRaisesRegex(OperatorError,'unmutated failed'):
                self.store.record_unchanged_resume(self.operation,locks,decision_hash=DIGEST,phase='unchanged_resume_started')
        self.assertEqual(self.store.status(self.operation)['state'],'recovery_required')

    def test_wrong_order_hash_and_lock_identity_have_no_journal_effect(self):
        with self.locks() as locks:
            self.drain(locks);self.store.fail(self.operation,locks,code='BACKUP_FAILED')
            before=self.store.status(self.operation)
            for phase,digest in [('unchanged_release_ready',DIGEST),('completed',DIGEST),('unchanged_resume_started','invalid')]:
                with self.assertRaises(OperatorError):self.store.record_unchanged_resume(self.operation,locks,decision_hash=digest,phase=phase)
            self.assertEqual(self.store.status(self.operation),before)
        with OperationLocks(self.root/'locks',self.state['deployment_id'],[ident(999)]) as wrong,self.assertRaisesRegex(OperatorError,'exact independent'):
            self.store.record_unchanged_resume(self.operation,wrong,decision_hash=DIGEST,phase='unchanged_resume_started')

    def test_recovery_attempt_keeps_conservative_fence_and_original_authority_revoked(self):
        with self.locks() as locks:
            self.drain(locks);self.store.fail(self.operation,locks,code='MUTATION_FAILED')
            for phase in ['unchanged_resume_started','unchanged_release_ready','unchanged_traffic_resumed']:
                self.store.record_unchanged_resume(self.operation,locks,decision_hash=DIGEST,phase=phase)
        with self.locks() as locks:
            self.store.record_unchanged_resume(self.operation,locks,decision_hash='sha256:'+'b'*64,phase='unchanged_resume_started')
            self.assertTrue(self.store.status(self.operation)['traffic_resumed'])
            self.assertFalse(self.store.status(self.operation)['mutation_started'])

    def test_new_action_uses_existing_exact_private_review_and_revocation(self):
        reviews=RecoveryReviews(self.store);payload=dict(schema_version=1,action='resume_unchanged_release',operation_id=self.operation,base_state_digest=DIGEST)
        decision=reviews.issue(payload);digest=data_digest(decision)
        reviews.verify(decision,exact_hash=digest,current_payload=payload)
        with self.assertRaisesRegex(OperatorError,'actual state changed'):
            reviews.verify(decision,exact_hash=digest,current_payload=payload|{'base_state_digest':'changed'})
        reviews.revoke(decision,exact_hash=digest)
        with self.assertRaisesRegex(OperatorError,'revoked'):reviews.verify(decision,exact_hash=digest,current_payload=payload)


class WorkerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.config=dict(project='mp-r0-r1test',worker_id='a'*64,image_id='sha256:'+'b'*64,sites=[dict(database='mp_disposable_r0_r1_test')])
        self.info=dict(Id='a'*64,Image=self.config['image_id'],Mounts=[dict(Destination='/run/secrets',Type='volume',Name='mp-r0-r1test_appconfig',RW=False),dict(Destination='/var/lib/modular',Type='volume',Name='mp-r0-r1test_filestore',RW=True)],
            Config=dict(User='10001:10001',Entrypoint=['/venv/bin/python'],Cmd=['-c',(ROOT/'packages/platform_sdk/modular_platform/worker_start.py').read_text(encoding='utf8'),self.config['sites'][0]['database'],DIGEST]),
            HostConfig=dict(ReadonlyRootfs=True,CapDrop=['ALL'],SecurityOpt=['no-new-privileges']),NetworkSettings=dict(Networks={'mp-r0-r1test_runtime':{}}))

    def test_exact_guarded_worker_is_accepted(self):validate_base_worker(self.info,self.config,DIGEST)

    def test_changed_code_pin_database_or_maintenance_arguments_are_rejected(self):
        for index,value in [(0,'-u'),(1,'arbitrary code'),(2,'another_database'),(3,'sha256:'+'c'*64)]:
            changed=copy.deepcopy(self.info);changed['Config']['Cmd'][index]=value
            with self.subTest(index=index),self.assertRaises(OperatorError):validate_base_worker(changed,self.config,DIGEST)

    def test_wrong_worker_image_mount_or_network_is_rejected(self):
        changes=[('Id','c'*64),('Image','sha256:'+'c'*64),('Mounts',self.info['Mounts']+[dict(Destination='/var/run/docker.sock',Type='bind',RW=True)]),('NetworkSettings',dict(Networks={'other':{}}))]
        for key,value in changes:
            changed=copy.deepcopy(self.info);changed[key]=value
            with self.subTest(key=key),self.assertRaises(OperatorError):validate_base_worker(changed,self.config,DIGEST)

    def test_root_writable_source_or_missing_security_options_are_rejected(self):
        for section,key,value in [('Config','User','root'),('HostConfig','ReadonlyRootfs',False),('HostConfig','CapDrop',None),('HostConfig','SecurityOpt',None)]:
            changed=copy.deepcopy(self.info);changed[section][key]=value
            with self.subTest(key=key),self.assertRaises(OperatorError):validate_base_worker(changed,self.config,DIGEST)

    def test_uncertain_mutation_unknown_phase_or_unexplained_traffic_is_rejected(self):
        base=dict(state='failed_before_mutation',mutation_started=False,traffic_resumed=False,phase='checkpointed');validate_failed_base(base)
        for change in [dict(state='running'),dict(mutation_started=True),dict(phase='migrated'),dict(traffic_resumed=True)]:
            with self.subTest(change=change),self.assertRaises(OperatorError):validate_failed_base(base|change)
        validate_failed_base(base|dict(traffic_resumed=True,phase='unchanged_resume_started'))


if __name__=='__main__':unittest.main()
