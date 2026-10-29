"""Private scheduler inputs cannot broaden scopes, inject names or leak bad data."""
import secrets
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.durable import DispatchScope,QueueError,enqueue,append_event,claim


class DurableValidationTests(unittest.TestCase):
    def setUp(self):
        self.cr=Mock()
        self.scope=DispatchScope(str(uuid4()),1,2,3,'sha256:'+'a'*64)

    def test_unvalidated_scope_and_bool_row_ids_fail_before_any_SQL(self):
        with self.assertRaises(QueueError):DispatchScope(str(uuid4()),True,2,3,'sha256:'+'a'*64)
        with self.assertRaises(QueueError):enqueue(self.cr,{},'org.example.test',1,{},'one')
        self.cr.execute.assert_not_called()

    def test_invalid_or_oversize_payload_is_redacted_and_never_queued(self):
        secret=secrets.token_urlsafe(32)
        for payload in [{'secret':secret,'number':float('nan')},{'text':secret*3000}]:
            with self.assertRaises(QueueError) as raised:
                enqueue(self.cr,self.scope,'org.example.test',1,payload,'one')
            self.assertNotIn(secret,str(raised.exception))
        self.cr.execute.assert_not_called()

    def test_unregistered_name_bounds_or_effect_policy_never_reach_SQL(self):
        for handler,version,mode in [('x; DROP TABLE mp_job',1,'idempotent'),('org.example.test',True,'idempotent'),('org.example.test',1,'pretend_exactly_once')]:
            with self.assertRaises(QueueError):enqueue(self.cr,self.scope,handler,version,{},'one',effect_mode=mode)
        with self.assertRaises(QueueError):claim(self.cr,str(uuid4()),self.scope.release_digest,str(uuid4()),[])
        self.cr.execute.assert_not_called()

    def test_invalid_event_scope_sequence_or_identity_is_not_published(self):
        for sequence in [True,0,-1]:
            with self.assertRaises(QueueError):append_event(self.cr,self.scope,plugin_id='org.example.notes',topic='org.example.notes.changed',version=1,aggregate_id=str(uuid4()),payload={},correlation_id=str(uuid4()),sequence=sequence)
        self.cr.execute.assert_not_called()


if __name__=='__main__':unittest.main()
