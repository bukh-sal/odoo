"""Native restore orchestration: late queue checks and pre-enable journal fence."""
import copy,json
from unittest.mock import Mock,patch
import unittest
import test_restore_dispatch as legacy
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest


class NativeDispatchResumeTests(unittest.TestCase):
    def setUp(self):
        self.base=legacy.RestoreDispatchTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        b=self.base;b.effects.update(job_table=True,outbox_table=True);b.authority['has_dispatch_tables']=True
        self.snapshot=dict(profile='r1-native-dispatch-v1',schema_digest='sha256:'+'a'*64,release_digest='sha256:'+'b'*64,state_digest='sha256:'+'c'*64,
            control=dict(state='paused',generation=7),tables={},uncertain_jobs=0)
        path=b.root/'recoveries'/b.op/'result.json';result=json.loads(path.read_text());result['dispatch']=copy.deepcopy(self.snapshot);path.write_text(json.dumps(result))
        self.helper=Mock();self.helper.inspect_current.side_effect=lambda **kwargs:copy.deepcopy(self.snapshot)
        self.helper.require_native.side_effect=lambda value,**kwargs:value
        def enable(*args,**kwargs):b.timeline.append('enable');return dict(dispatch_enabled=True)
        self.helper.run.side_effect=enable
        p=patch('modular_platform.dispatch_operator.DispatchMaintenance',return_value=self.helper);p.start();self.addCleanup(p.stop)
    def decision(self):
        value=self.base.decision();value['review']['review_id']='00000000-0000-4000-8000-000000000901';return value
    def test_journal_fence_precedes_dispatch_and_ingress(self):
        decision=self.decision();self.base.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.base.timeline,['journal','enable','start-edge'])
        self.assertEqual(self.helper.run.call_args.kwargs['expected_digest'],self.snapshot['state_digest'])
    def test_enable_failure_does_not_open_ingress_or_erase_effects_fence(self):
        def failure(*args,**kwargs):self.base.timeline.append('enable-failed');raise OperatorError('Interrupted enable')
        self.helper.run.side_effect=failure;decision=self.decision()
        with self.assertRaises(OperatorError):self.base.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.base.timeline,['journal','enable-failed'])
    def test_late_queue_change_rejects_before_journal_or_enable(self):
        decision=self.decision();self.base.readiness_change=lambda:self.snapshot.update(state_digest='sha256:'+'d'*64)
        with self.assertRaises(OperatorError):self.base.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.assertEqual(self.base.timeline,[]);self.helper.run.assert_not_called()
    def test_legacy_result_does_not_silently_admit_dispatch_tables(self):
        b=self.base;path=b.root/'recoveries'/b.op/'result.json';result=json.loads(path.read_text());result.pop('dispatch');path.write_text(json.dumps(result))
        with self.assertRaises(OperatorError):b.recovery._resume_state(b.op)
        self.helper.run.assert_not_called();self.assertEqual(b.timeline,[])
