"""Inspection observations cannot assert execution or native registry liveness."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.contracts import ContractError,validate,validate_operations_view,plan_hash

EXAMPLES=ROOT/'packages/contracts/examples/v1'
def example(name):return json.loads((EXAMPLES/(name+'.json')).read_text(encoding='utf-8'))

class ManagerContracts(unittest.TestCase):
    def test_new_examples_and_unchanged_old_consumers(self):
        for name in ('manager-view','manager-view-details','manager-view-upload','manager-view-external'):validate('manager-view',example(name))
        for name in ('operations-view','operations-view-status'):validate_operations_view(example(name))
        self.assertEqual(plan_hash(example('plan')),(EXAMPLES/'plan.sha256').read_text().strip())

    def test_unknown_authority_and_unsupported_major(self):
        for name in ('manager-view','manager-view-details','manager-view-upload'):
            for key in ('approved','command','password','database','endpoint_url','operator_id'):
                v=example(name);v[key]=True
                with self.subTest(name=name,key=key),self.assertRaises(ContractError):validate('manager-view',v)
            v=example(name);v['schema_version']=2
            with self.assertRaises(ContractError):validate('manager-view',v)

    def test_upload_cannot_claim_retention_execution_or_unchecked_success(self):
        for key,value in [('retained',True),('executed',True),('artifact',None),('validation_scope','trust_gate'),('error_code','NOT_CURATED')]:
            v=example('manager-view-upload');v[key]=value
            with self.subTest(key=key),self.assertRaises(ContractError):validate('manager-view',v)
        v=example('manager-view-upload');v.update(result='not_curated',validation_scope='trust_gate',artifact=None,error_code='NOT_CURATED');validate('manager-view',v)
        v['result']='invalid'
        with self.assertRaises(ContractError):validate('manager-view',v)
        v.update(validation_scope='archive_rejected',error_code='INVALID_ARCHIVE');validate('manager-view',v)

    def test_health_publisher_and_unloading_claims_are_bounded(self):
        v=example('manager-view');v['items'][0]['health']['state']='healthy'
        with self.assertRaises(ContractError):validate('manager-view',v)
        for path in ('publisher','unloads'):
            v=example('manager-view-details')
            if path=='publisher':v['provenance']['publisher_identity_verified']=True
            else:v['feature_suspension_unloads_code']=True
            with self.assertRaises(ContractError):validate('manager-view',v)

    def test_external_healthy_observation_is_not_native_or_removed_success(self):
        value=example('manager-view-external');validate('manager-view',value)
        for key,field in [('runtime','native'),('metadata_state','removed'),('database_state','failed')]:
            v=copy.deepcopy(value);v['items'][0][key]=field
            with self.subTest(key=key),self.assertRaises(ContractError):validate('manager-view',v)
        value['approved']=True
        with self.assertRaises(ContractError):validate('manager-view',value)

    def test_pagination_payload_and_identity_limits(self):
        v=example('manager-view');v['items']*=21
        with self.assertRaises(ContractError):validate('manager-view',v)
        for key,value in [('size',100*1024*1024+1),('artifact_digest','sha256:'+'a'*64+'\n')]:
            v=example('manager-view-upload');v[key]=value
            with self.assertRaises(ContractError):validate('manager-view',v)
        v=example('manager-view-details');v['manifest']['installer_command']='run'
        with self.assertRaises(ContractError):validate('manager-view',v)

if __name__=='__main__':unittest.main()
