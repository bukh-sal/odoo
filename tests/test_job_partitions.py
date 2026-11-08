"""Private partition identities cannot broaden workspace or native scope."""
import json
from pathlib import Path
import sys
import unittest
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
from modular_platform import durable,job_fairness
from modular_platform.capacity_advisor import advise,CapacityError
import test_capacity_advisor as capacity_test


class PartitionTests(unittest.TestCase):
    def test_keys_preserve_kind_and_reject_ambiguous_identities(self):
        for kind in ('native','workspace'):
            partition=durable.ExecutionPartition(kind,1)
            self.assertEqual(durable.ExecutionPartition.from_key(partition.key),partition)
        for value in ('n:1','n:0000000000','w:2147483648','w:-000000001','x:0000000001',None,True):
            with self.assertRaises(durable.QueueError):durable.ExecutionPartition.from_key(value)
        for ident in (True,False,0,-1,None):
            with self.assertRaises(durable.QueueError):durable.ExecutionPartition('native',ident)

    def test_rotations_are_only_bounded_hints_for_the_current_release(self):
        release='sha256:'+'a'*64
        raw=json.dumps(dict(release=release,partition='n:0000000001',token=str(uuid4())))
        self.assertEqual(job_fairness._partition_after(raw,release),'n:0000000001')
        self.assertEqual(job_fairness._partition_after(raw,'sha256:'+'b'*64),'')
        for value in ('null','[]','true','{"partition":"n:1"}'):
            self.assertEqual(job_fairness._partition_after(value,release),'')
        with self.assertRaises(durable.QueueError):job_fairness._partition_after('x'*513,release)

    def test_capacity_distinguishes_native_installations_and_refuses_missing_or_mixed_scope(self):
        observation,policy=capacity_test.fixtures()
        for ident,group in enumerate(observation['groups'],1):
            group.update(workspace=None,partition=durable.ExecutionPartition('native',ident).key)
        result=advise(observation,policy,now=capacity_test.NOW,expected_pins={'release':'a'})
        self.assertEqual(result['pools']['bulk']['partition_slots'],6)
        observation['groups'][0]['partition']='w:0000000001'
        with self.assertRaises(CapacityError):advise(observation,policy,now=capacity_test.NOW)
        del observation['groups'][0]['partition']
        with self.assertRaises(CapacityError):advise(observation,policy,now=capacity_test.NOW)


if __name__=='__main__':unittest.main()
