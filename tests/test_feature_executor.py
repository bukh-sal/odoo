"""Feature journal describes metadata changes and never native migration."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperationLocks,OperatorError
from modular_platform.plans import prepare_plan
from modular_platform.app_channel import journal_view
from test_plans import base_state,solution,target,ident,STAMP
from test_resolution import plugin


class FeatureJournal(unittest.TestCase):
    def setUp(self):
        self.catalog=[plugin('a')];self.state=base_state(self.catalog)
        self.state.update(bindings=[],endpoints=[])
        self.target=target(action='suspend')
        self.state['installations']=[{key:value for key,value in self.target.items() if key!='action'}|
            {'state':'installed','feature_state':'enabled','metadata_state':'installed'}]
        self.bundle=prepare_plan(self.state,self.state['release_lock'],solution(self.catalog),[self.target],
            operation_type='suspend',operation_id=ident(500),created_at=STAMP)

    def test_metadata_sequence_blocks_fake_migration_and_fences_possible_live_traffic(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=OperatorStore.initialize(Path(temporary)/'control',{self.state['deployment_id']:self.state['site_ids']})
            revalidate=lambda _:copy.deepcopy(self.state)
            operation=store.register(self.bundle,revalidate)
            origin={'operation_id':operation,'site_id':self.state['site_ids'][0],'plan_hash':self.bundle['plan_hash'],
                'requested_by':ident(90),'request_id':ident(91)}
            with self.assertRaisesRegex(OperatorError,'differs from independent'):
                store.attach_application_request(operation,origin|{'site_id':ident(999)})
            store.attach_application_request(operation,origin)
            store.attach_application_request(operation,origin)
            with self.assertRaisesRegex(OperatorError,'origin is immutable'):
                store.attach_application_request(operation,origin|{'request_id':ident(92)})
            self.assertEqual(store.application_request(operation),origin)
            store.approve(operation,exact_hash=self.bundle['plan_hash'],
                acknowledgments={'destructive':False,'trust_expansion':False,'permission_expansion':False},revalidate=revalidate)
            with OperationLocks(store.root/'locks',self.state['deployment_id'],self.state['site_ids']) as held:
                store.reserve(operation,held,revalidate)
                with self.assertRaises(OperatorError):store.before_mutation(operation,held,revalidate)
                store.advance(operation,held,'staged')
                with self.assertRaisesRegex(OperatorError,'operation type'):store.advance(operation,held,'maintenance')
                store.before_mutation(operation,held,revalidate)
                self.assertTrue(store.status(operation)['traffic_resumed'])
                with self.assertRaisesRegex(OperatorError,'skipped'):store.advance(operation,held,'ready')
                for phase in ('metadata_published','ready','completed'):store.advance(operation,held,phase)
            status=store.status(operation)
            self.assertEqual(status['state'],'completed')
            self.assertFalse(any(item['code'] in ('migrated','workers_replaced') for item in status['history']))

    def test_public_mirror_is_typed_and_discards_private_details(self):
        status={'operation_id':ident(500),'plan_hash':self.bundle['plan_hash'],'state':'approved','phase':'prepared',
            'approval_expires_at':'2026-10-28T06:00:00Z','history':[{'sequence':1,'utc':STAMP,'code':'approved','details':{'private_diagnostic':'do not mirror'}}]}
        view=journal_view(self.bundle,status,{'requested_by':ident(99)},self.state)
        self.assertEqual(view['source'],'operator_journal_mirror')
        self.assertEqual(view['dimensions'][0]['database_state'],'installed')
        self.assertNotIn('details',view['history'][0])
        self.assertNotIn('private_diagnostic',str(view))


if __name__=='__main__':unittest.main()
