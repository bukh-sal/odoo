"""Restored effects and authority must remain safe through the final boundary."""
from contextlib import nullcontext
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.restore_executor import RestoreExecutor,EFFECTS_SELECT,AUTHORITY_SELECT

CLEAR=dict(job_table=False,outbox_table=False,api_key_count=0,active_technical_credentials=0,external_installations=0)


class RestoreDispatchTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.op='00000000-0000-4000-8000-000000000500'
        self.config=dict(sites=[dict(database='mp_disposable_r0_r1_restored')])
        self.store=Mock();self.store.root=self.root;self.store.policy={'allow_noninteractive':True};self.store.status.return_value=dict(state='revoked',phase='restore_verified',traffic_resumed=False)
        self.store.bundle.return_value=dict(plan=dict(deployment_id='00000000-0000-4000-8000-000000000010',site_ids=['00000000-0000-4000-8000-000000000020']))
        directory=self.root/'recoveries'/self.op;directory.mkdir(parents=True);(directory/'result.json').write_text(json.dumps(dict(configuration=self.config)),encoding='utf8')
        self.native=Mock();self.native.store=self.store;self.native.config=self.config
        self.native.observer._container.side_effect=lambda service,**kwargs:service
        self.native.observer.read.return_value=dict(sites=[],runtime=dict(inventory_digest='sha256:'+'a'*64))
        self.edge_open=False;self.native._inspect.side_effect=lambda edge:dict(State=dict(Running=self.edge_open))
        self.effects=copy.deepcopy(CLEAR);self.authority=dict(principals=[],memberships=[],operators=[],api_key_count=0,has_dispatch_tables=False)
        self.readiness_change=lambda:None;self.readiness_error=False;self.timeline=[]
        self.recovery=RestoreExecutor(self.native)
        self.reviews=Mock();self.reviews.verify.side_effect=self.verify
        self.store.record_restore_resume.side_effect=lambda *args,**kwargs:self.timeline.append('journal')
        patches=[patch('modular_platform.restore_executor._run',side_effect=self.execute_command),patch('modular_platform.restore_executor.OperationLocks',return_value=nullcontext(Mock())),patch('modular_platform.restore_executor.RecoveryReviews',return_value=self.reviews)]
        for item in patches:item.start();self.addCleanup(item.stop)

    def execute_command(self,args,*,input=None):
        if input==EFFECTS_SELECT.encode():return json.dumps(self.effects).encode()
        if input==AUTHORITY_SELECT.encode():return json.dumps(self.authority).encode()
        if args[:3]==['docker','exec','app']:
            if self.readiness_error:raise OperatorError('Readiness failed')
            self.readiness_change();return b''
        if args==['docker','start','edge']:self.timeline.append('start-edge');return b''
        self.fail('Unexpected recovery command')

    def verify(self,decision,*,exact_hash,current_payload):
        value=copy.deepcopy(decision);value.pop('review');self.assertEqual(value,current_payload);self.assertEqual(exact_hash,data_digest(decision))

    def decision(self):return self.recovery._resume_state(self.op)|dict(review={'fixture':'independent review semantics covered by real-store tests'})

    def test_clear_profile_binds_effects_and_human_authority_without_writes(self):
        value=self.recovery._resume_state(self.op)
        self.assertEqual(value['effects'],CLEAR);self.assertEqual(value['recovery_profile'],'r1-no-dispatch-v1');self.assertEqual(value['authority_digest'],data_digest(self.authority));self.assertEqual(self.timeline,[])

    def test_each_unsupported_effect_denies_a_resume_proposal(self):
        for key in CLEAR:
            self.effects=copy.deepcopy(CLEAR);self.effects[key]=True if key.endswith('_table') else 1
            with self.subTest(key=key),self.assertRaisesRegex(OperatorError,'require reconciliation'):self.recovery._resume_state(self.op)
        self.store.record_restore_resume.assert_not_called();self.assertEqual(self.timeline,[])

    def test_malformed_effect_snapshot_fails_closed(self):
        for value in [{},None,[],dict(CLEAR,api_key_count=-1),dict(CLEAR,job_table=None),dict(CLEAR,unexpected=False)]:
            self.effects=value
            with self.subTest(value=value),self.assertRaises(OperatorError):self.recovery._supported_effects('fresh')

    def test_queue_arriving_after_readiness_stays_before_traffic_fence(self):
        decision=self.decision();self.readiness_change=lambda:self.effects.update(outbox_table=True)
        with self.assertRaisesRegex(OperatorError,'require reconciliation'):self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.store.record_restore_resume.assert_not_called();self.assertEqual(self.timeline,[])

    def test_technical_identity_reappearing_after_readiness_stays_fenced(self):
        decision=self.decision();self.readiness_change=lambda:self.effects.update(active_technical_credentials=1)
        with self.assertRaisesRegex(OperatorError,'require reconciliation'):self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.store.record_restore_resume.assert_not_called();self.assertEqual(self.timeline,[])

    def test_authority_changed_after_readiness_invalidates_review(self):
        decision=self.decision();self.readiness_change=lambda:self.authority['operators'].append(dict(principal_id='operator',state='revoked'))
        with self.assertRaisesRegex(OperatorError,'changed before traffic'):self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.store.record_restore_resume.assert_not_called();self.assertEqual(self.timeline,[])

    def test_already_open_or_late_open_edge_requires_reconciliation(self):
        self.edge_open=True
        with self.assertRaisesRegex(OperatorError,'already open'):self.recovery._resume_state(self.op)
        self.edge_open=False;decision=self.decision();self.readiness_change=lambda:setattr(self,'edge_open',True)
        with self.assertRaisesRegex(OperatorError,'already open'):self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.timeline,[])

    def test_readiness_error_cannot_record_open_traffic(self):
        decision=self.decision();self.readiness_error=True
        with self.assertRaisesRegex(OperatorError,'Readiness failed'):self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.timeline,[])

    def test_clean_resume_records_conservative_fence_before_edge_start(self):
        decision=self.decision();result=self.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(result['state'],'restored_traffic_resumed');self.assertEqual(self.timeline,['journal','start-edge'])
        self.reviews.verify.assert_called_once();self.reviews.check_reserved.assert_called_once()


if __name__=='__main__':unittest.main()
