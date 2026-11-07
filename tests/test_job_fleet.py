"""Reviewed fleet crash recovery, stale decisions and maintenance boundaries."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'packages/platform_sdk'))
from modular_platform.job_fleet import JobFleet
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_os import OperatorError, protect_directory


class FleetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = protect_directory(Path(temporary.name)/'control')
        self.op = SimpleNamespace(records=protect_directory(root/'job-controls'),
            deployment='00000000-0000-4000-8000-000000000001',
            site=dict(site_id='00000000-0000-4000-8000-000000000002', database='test'),
            project='test-project', target=dict(image_id='sha256:'+'a'*64, published_release={'generation':1}),
            store=SimpleNamespace(root=root, policy={'maximum_start_lifetime':600}),
            runtime=Mock(return_value={'inventory_digest':'sha256:'+'b'*64}),
            _lanes=Mock(return_value={}), docker=Mock(return_value=json.dumps(dict(NCPU=8,MemTotal=8*1024**3)).encode()))
        self.fleet = JobFleet(self.op)

    def review(self, **kw):
        return self.fleet.review(**kw)['approval']

    def test_interrupted_intent_before_desired_is_resumable(self):
        approval = self.review()
        with patch.object(self.fleet,'_save',side_effect=OSError('simulated host interruption')):
            with self.assertRaises(OSError):self.fleet.apply(approval)
        self.assertIsNone(self.fleet.desired())
        with patch.object(self.fleet,'reconcile',return_value={'state':'ready'}):
            self.assertEqual(self.fleet.apply(approval),{'state':'ready'})
        self.assertEqual(self.fleet.desired()['approval'],approval)

    def test_partial_start_replays_current_intent_and_keeps_generation(self):
        approval = self.review()
        with patch.object(self.fleet,'reconcile',side_effect=OperatorError('second container refused')):
            with self.assertRaises(OperatorError):self.fleet.apply(approval)
        before = self.fleet.desired()
        with patch.object(self.fleet,'reconcile',return_value={'state':'ready'}) as reconcile:
            self.fleet.apply(approval)
        reconcile.assert_called_once_with()
        self.assertEqual(self.fleet.desired(),before)

    def test_changed_release_refuses_review_without_reconciling(self):
        approval = self.review()
        self.op.target['published_release']['generation'] += 1
        with patch.object(self.fleet,'reconcile') as reconcile:
            with self.assertRaisesRegex(OperatorError,'pins'):self.fleet.apply(approval)
        reconcile.assert_not_called()
        self.assertIsNone(self.fleet.desired())

    def test_old_attempt_cannot_replace_later_profile(self):
        first = self.review()
        with patch.object(self.fleet,'reconcile',return_value={'state':'ready'}):
            self.fleet.apply(first)
            later = self.review(bulk_lanes=3)
            self.fleet.apply(later)
            with self.assertRaisesRegex(OperatorError,'reconciliation'):self.fleet.apply(first)
        self.assertEqual(self.fleet.desired()['approval'],later)

    def test_container_change_invalidates_unattempted_review(self):
        approval = self.review()
        self.op._lanes.return_value={'unreviewed':dict(Id='new',Image='other',Config={},HostConfig={},State={'Running':True})}
        with self.assertRaisesRegex(OperatorError,'changed after'):self.fleet.apply(approval)
        self.assertIsNone(self.fleet.desired())

    def test_drain_is_persisted_before_docker_and_old_apply_does_not_reactivate(self):
        approval = self.review()
        with patch.object(self.fleet,'reconcile',return_value={'state':'ready'}):self.fleet.apply(approval)
        with patch.object(self.fleet,'reconcile',side_effect=OperatorError('Docker unavailable')):
            with self.assertRaises(OperatorError):self.fleet.drain()
        self.assertEqual(self.fleet.desired()['state'],'paused')
        with patch.object(self.fleet,'reconcile',return_value={'state':'paused'}):self.fleet.apply(approval)
        self.assertEqual(self.fleet.desired()['state'],'paused')

    def test_release_maintenance_requires_paused_and_stopped_roles(self):
        approval = self.review()
        with patch.object(self.fleet,'reconcile',return_value={'state':'ready'}):self.fleet.apply(approval)
        native=NativeExecutor.__new__(NativeExecutor)
        native.store=self.op.store
        native.config=dict(sites=[self.op.site],deployment_id=self.op.deployment)
        with patch('modular_platform.native_executor._run') as docker:
            with self.assertRaisesRegex(OperatorError,'Pause and drain'):native._require_jobs_drained()
            docker.assert_not_called()
        desired=self.fleet.desired();desired['state']='paused';self.fleet._save(desired)
        with patch('modular_platform.native_executor._run',side_effect=[b'lane',json.dumps([{'State':{'Running':True}}]).encode()]):
            with self.assertRaisesRegex(OperatorError,'stopped'):native._require_jobs_drained()
        with patch('modular_platform.native_executor._run',return_value=b''):native._require_jobs_drained()


if __name__=='__main__':unittest.main()
