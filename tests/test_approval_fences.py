"""Approval boundaries not covered by initial start-only source tests."""
import copy,json,sqlite3,sys,tempfile,unittest
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tests')]
from modular_platform.contracts import ContractError
from modular_platform.operator_os import OperationLocks,OperatorError
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import prepare_plan,data_digest
from test_plans import base_state,solution,target,ident,STAMP
from test_resolution import plugin

class ApprovalBoundaryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.catalog=[plugin('a')];self.state=base_state(self.catalog);t=target(action='suspend');self.state.update(bindings=[],endpoints=[],security_metadata_digest='sha256:'+'a'*64,catalog_validation_digest=data_digest(self.state['release_lock']['plugins']));self.state['installations']=[{k:v for k,v in t.items() if k!='action'}|dict(state='installed',metadata_state='installed',feature_state='enabled')]
  self.bundle=prepare_plan(self.state,self.state['release_lock'],solution(self.catalog),[t],operation_type='suspend',operation_id=ident(500),created_at=STAMP)
  self.store=OperatorStore.initialize(Path(self.temp.name)/'control',{self.state['deployment_id']:self.state['site_ids']});self.validate=lambda _:copy.deepcopy(self.state);self.op=self.store.register(self.bundle,self.validate);self.approval=self.store.approve(self.op,exact_hash=self.bundle['plan_hash'],acknowledgments=dict(destructive=False,trust_expansion=False,permission_expansion=False),revalidate=self.validate)
 def locks(self):return OperationLocks(self.store.root/'locks',self.state['deployment_id'],self.state['site_ids'])
 def snapshot(self):
  with closing(sqlite3.connect(self.store.database)) as db:return list(db.execute('SELECT * FROM operations')),list(db.execute('SELECT * FROM events'))
 def test_exact_expiry_after_reservation_cannot_enter_mutation(self):
  expiry=datetime.fromisoformat(self.approval['expires_at'].replace('Z','+00:00'))
  with self.locks() as held:
   self.store.reserve(self.op,held,self.validate);self.store.advance(self.op,held,'staged');before=self.snapshot()
   with self.assertRaisesRegex(ContractError,'Approval unavailable'):self.store.before_mutation(self.op,held,self.validate,now=expiry)
   self.assertEqual(before,self.snapshot());self.assertFalse(self.store.status(self.op)['mutation_started'])
 def test_current_base_security_bindings_endpoints_policy_release_and_catalog_rechecked_before_mutation(self):
  with self.locks() as held:
   self.store.reserve(self.op,held,self.validate);self.store.advance(self.op,held,'staged');before=self.snapshot()
   changes=dict(generation=2,release_digest='sha256:'+'f'*64,security_metadata_digest='sha256:'+'c'*64,catalog_validation_digest='sha256:'+'d'*64,bindings=[dict(generation=2)],endpoints=[dict(generation=2)],installations=[],policy_version=2,operator_authorization_generation=2,site_ids=[ident(999)])
   for field,value in changes.items():
    with self.subTest(field=field):
     with self.assertRaisesRegex(ValueError,'Stale plan'):self.store.before_mutation(self.op,held,lambda _:{**copy.deepcopy(self.state),field:value})
     self.assertEqual(before,self.snapshot())
 def test_transplanted_valid_approval_cannot_start_another_operation(self):
  other=copy.deepcopy(self.bundle);other['plan']['operation_id']=ident(501);other['operation_lock']['operation_id']=ident(501)
  from modular_platform.plans import data_digest,_display
  from modular_platform.contracts import plan_hash
  other['plan']['dependency_lock_digest']=data_digest(other['operation_lock']);other['plan_hash']=plan_hash(other['plan']);other['display']=_display(other['plan'],other['operation_lock']);self.store.register(other,self.validate)
  with self.store._connect(transaction=True) as db:db.execute('UPDATE operations SET approval=?,state=? WHERE operation_id=?',(json.dumps(self.approval),'approved',ident(501)))
  before=self.snapshot()
  with self.locks() as held:
   with self.assertRaisesRegex(OperatorError,'identity/hash mismatch'):self.store.reserve(ident(501),held,self.validate)
  self.assertEqual(before,self.snapshot());self.assertFalse(self.store.status(ident(501))['mutation_started'])

if __name__=='__main__':unittest.main()
