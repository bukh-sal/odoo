"""Actual footprint construction/guards; SQL semantics have a separate PG witness."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.checkpoint_effects import observe_effects,require_same_effects,validate_footprint,_table_sql
from modular_platform.dispatch_lifecycle import PHYSICAL_SCHEMA
from modular_platform.plans import data_digest
from modular_platform.operator_os import OperatorError


class Cursor:
    def __init__(self,isolation='repeatable read',readonly='on',leased=0):
        self.isolation,self.readonly,self.leased=isolation,readonly,leased;self.queries=[]
    def execute(self,sql):self.queries.append(sql)
    def fetchone(self):
        sql=self.queries[-1]
        if sql=='SHOW transaction_isolation':return (self.isolation,)
        if sql=='SHOW transaction_read_only':return (self.readonly,)
        if "state='leased'" in sql:return (self.leased,)
        return (1,'a'*64)


class CheckpointEffects(unittest.TestCase):
    def setUp(self):
        self.scope=SimpleNamespace(site_id='00000000-0000-4000-8000-000000000121')
        self.tables={name:dict(rows=1,sha256='b'*64) for name in ['mp_dispatch_control','mp_job','mp_outbox','mp_event_delivery']}
        self.snapshot=dict(profile='r1-native-dispatch-v1',external_installations=0,active_credentials=0,api_keys=0,
            uncertain_jobs=0,recurring_schedules=0,job_states={'completed':1},tables=self.tables,
            schema_digest=data_digest({name:PHYSICAL_SCHEMA[name] for name in self.tables}))
        p=patch('modular_platform.checkpoint_effects.observe',side_effect=lambda *args:self.snapshot)
        p.start();self.addCleanup(p.stop)

    def packet(self,cr=None):return observe_effects(cr or Cursor(),self.scope)

    def test_actual_builder_ignores_only_fixed_epochs_and_keeps_all_other_tables(self):
        cr=Cursor();packet=self.packet(cr)
        self.assertNotIn('mp_dispatch_control',packet['tables'])
        self.assertEqual(packet['tables']['mp_job'],dict(rows=1,sha256='a'*64))
        self.assertEqual(packet['tables']['mp_event_delivery'],dict(rows=1,sha256='b'*64))
        job=next(q for q in cr.queries if 'FROM public.mp_job ' in q)
        self.assertIn("ARRAY['release_digest','dispatch_generation','claim_generation']",job)
        for name in ('state','result','attempts','error_code','lease_owner','payload'):
            self.assertNotIn("'"+name+"'",job)
        require_same_effects(packet,copy.deepcopy(packet))

    def test_delivery_job_receipt_or_history_digest_drift_and_table_drift_refuse(self):
        before=self.packet()
        for name in before['tables']:
            altered=copy.deepcopy(before);altered['tables'][name]['sha256']='c'*64
            altered['digest']=data_digest({k:v for k,v in altered.items() if k!='digest'})
            with self.assertRaisesRegex(OperatorError,'semantic effects differ'):require_same_effects(before,altered)
        for name in ('mp_event_consumption','mp_job_identity','mp_event_history'):
            altered=copy.deepcopy(before);altered['tables'][name]=dict(rows=1,sha256='d'*64)
            schema={'mp_dispatch_control':PHYSICAL_SCHEMA['mp_dispatch_control'],**{t:PHYSICAL_SCHEMA[t] for t in altered['tables']}}
            altered['schema_digest']=data_digest(schema);altered['digest']=data_digest({k:v for k,v in altered.items() if k!='digest'})
            with self.assertRaisesRegex(OperatorError,'semantic effects differ'):require_same_effects(before,altered)

    def test_running_uncertain_external_credential_and_recurrence_states_refuse(self):
        for key in ['external_installations','active_credentials','api_keys','uncertain_jobs','recurring_schedules']:
            with self.subTest(key=key):
                original=self.snapshot[key];self.snapshot[key]=1
                with self.assertRaises(OperatorError):self.packet()
                self.snapshot[key]=original
        self.snapshot['job_states']={'running':1}
        with self.assertRaisesRegex(OperatorError,'Running native'):self.packet()
        self.snapshot['job_states']={'pending':1}
        self.packet()
        with self.assertRaisesRegex(OperatorError,'Leased event'):self.packet(Cursor(leased=1))

    def test_inconsistent_or_writable_transaction_and_unknown_sql_refuse(self):
        for cr in (Cursor(isolation='read committed'),Cursor(readonly='off')):
            with self.assertRaises(OperatorError):self.packet(cr)
        with self.assertRaises(OperatorError):_table_sql('mp_job; DROP TABLE anything')

    def test_unknown_schema_malformed_rows_site_or_digest_refuse(self):
        self.snapshot['schema_digest']='forged'
        with self.assertRaisesRegex(OperatorError,'known core-effect schema'):self.packet()
        self.snapshot['schema_digest']=data_digest({name:PHYSICAL_SCHEMA[name] for name in self.tables})
        packet=self.packet()
        for change in [dict(site_id='foreign'),dict(schema_digest='forged'),dict(digest='forged')]:
            with self.assertRaises(OperatorError):validate_footprint(packet|change)
        malformed=copy.deepcopy(packet);malformed['tables']['mp_job']['rows']=True
        with self.assertRaisesRegex(OperatorError,'Invalid core-effect'):validate_footprint(malformed)


if __name__=='__main__':unittest.main()
