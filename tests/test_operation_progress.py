"""Independent observation is informative, bounded and cannot claim an outcome."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from operation_progress import observe_execution,read_observation
from modular_platform.operator_os import protect_directory,LockBusy
from modular_platform.operator_store import OperatorStore

class Store:
    _regular=staticmethod(OperatorStore._regular)
    def __init__(self,root):self.root=root;self.operation=str(uuid4());self.plan_hash='sha256:'+'a'*64
    def bundle(self,operation):
        if operation!=self.operation:raise ValueError('unknown operation')
        return dict(plan_hash=self.plan_hash)

class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(protect_directory(Path(self.temp.name)/'control'));self.op=self.store.operation
    def observation(self):return read_observation(self.store,self.op)
    def test_legacy_absent_is_unknown_not_failed(self):
        self.assertEqual(self.observation()['state'],'not_recorded')
    def test_actual_context_returns_without_claiming_journal_success(self):
        # Keep real locks/files/thread, but do not derive synthetic ages from a
        # timestamp that the concurrent real-clock heartbeat can advance.
        with patch('operation_progress._now',return_value=datetime.now(timezone.utc)):
            with observe_execution(self.store,self.op,'apply'):
                live=self.observation();self.assertEqual(live['state'],'observing');self.assertEqual(live['action'],'apply')
                observed=datetime.fromisoformat(live['observed_at'])
                self.assertEqual(read_observation(self.store,self.op,now=observed+timedelta(seconds=21))['state'],'stale')
                self.assertEqual(read_observation(self.store,self.op,now=observed-timedelta(seconds=1))['state'],'clock_changed')
            result=self.observation();self.assertEqual(result['state'],'returned');self.assertNotIn('completed',result)
    def test_newer_heartbeat_age_uses_latest_record_not_prior_read(self):
        with observe_execution(self.store,self.op,'apply'):pass
        # The real writer has joined. Supply a valid newer heartbeat fixture
        # without racing it, preserving actual private-file/binding validation.
        path=self.store.root/'progress'/(self.op+'.json');value=json.loads(path.read_bytes())
        earlier=datetime.fromisoformat(value['observed_at'])
        value.update(state='observing',observed_at=(earlier+timedelta(seconds=5)).isoformat(),elapsed_seconds=value['elapsed_seconds']+5)
        path.write_text(json.dumps(value))
        fresh=read_observation(self.store,self.op,now=earlier+timedelta(seconds=21))
        self.assertEqual(fresh['state'],'observing');self.assertEqual(fresh['age_seconds'],16)
        self.assertEqual(fresh['observation_state'],'observing');self.assertNotIn('completed',fresh)
        self.assertEqual(read_observation(self.store,self.op,now=earlier+timedelta(seconds=26))['state'],'stale')
        self.assertEqual(read_observation(self.store,self.op,now=earlier+timedelta(seconds=4))['state'],'clock_changed')
    def test_exception_retained_and_no_automatic_retry(self):
        calls=[]
        with self.assertRaisesRegex(RuntimeError,'original executor exception'):
            with observe_execution(self.store,self.op,'restore'):
                calls.append(1);raise RuntimeError('original executor exception')
        self.assertEqual(calls,[1]);self.assertEqual(self.observation()['state'],'interrupted')
    def test_second_writer_refused(self):
        with observe_execution(self.store,self.op,'apply'):
            with self.assertRaises(LockBusy):
                with observe_execution(self.store,self.op,'apply'):self.fail('concurrent writer')
    def test_wrong_plan_and_malformed_record_never_report_live(self):
        with observe_execution(self.store,self.op,'apply'):pass
        path=self.store.root/'progress'/(self.op+'.json');value=json.loads(path.read_bytes());value['plan_hash']='wrong';path.write_text(json.dumps(value))
        self.assertEqual(self.observation()['state'],'unavailable')
        path.write_text('null');self.assertEqual(self.observation()['state'],'unavailable')
    def test_final_diagnostic_failure_does_not_hide_executor_result(self):
        manager=observe_execution(self.store,self.op,'resume');manager.__enter__()
        with patch('operation_progress.os.replace',side_effect=OSError('diagnostic failure')):
            self.assertFalse(manager.__exit__(None,None,None))

if __name__=='__main__':unittest.main()
