"""G2 revision7: operator proposals/mirrors and canonical-end validation."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.contracts import CONTRACTS,ContractError,validate,validate_operations_view,plan_hash

EXAMPLES=ROOT/'packages/contracts/examples/v1'


def example(name):
    return json.loads((EXAMPLES/(name+'.json')).read_text())


class OperationContracts(unittest.TestCase):
    def test_additive_examples_embed_exact_plan_and_preserve_golden_hash(self):
        for name in ('operations-request','operations-request-submit'):
            validate('operations-request',example(name))
        for name in ('operations-view','operations-view-status'):
            validate_operations_view(example(name))
        original=json.loads((CONTRACTS/'plan.schema.json').read_text());original.pop('$id');original.pop('$schema')
        self.assertEqual(json.loads((CONTRACTS/'operations-view.schema.json').read_text())['$defs']['plan'],original)
        self.assertEqual(plan_hash(example('plan')),(EXAMPLES/'plan.sha256').read_text().strip())

    def test_unknown_authority_fields_and_protocol_majors_rejected(self):
        for fixture in ('operations-request','operations-request-submit'):
            for key in ('approved','operator_id','docker_socket','command','password','endpoint_url','database'):
                value=example(fixture);value[key]=True
                with self.subTest(fixture=fixture,key=key),self.assertRaises(ContractError):validate('operations-request',value)
            value=example(fixture);value['schema_version']=2
            with self.assertRaises(ContractError):validate('operations-request',value)

    def test_exact_artifacts_and_workspace_versus_site_scope(self):
        original=example('operations-request')
        for field in ('artifact_version','artifact_digest'):
            value=copy.deepcopy(original);del value[field]
            with self.assertRaises(ContractError):validate('operations-request',value)
        for operation in ('uninstall','unregister','remove'):
            value={**original,'operation_type':operation}
            with self.assertRaises(ContractError):validate('operations-request',value)
            value['workspace_ids']=[];value.pop('artifact_version')
            if operation!='remove':value.pop('artifact_digest')
            validate('operations-request',value)
        for operation in ('suspend','enable'):
            value={**original,'operation_type':operation,'workspace_ids':[]}
            with self.assertRaises(ContractError):validate('operations-request',value)
            value['workspace_ids']=original['workspace_ids'];value.pop('artifact_version');value.pop('artifact_digest')
            validate('operations-request',value)
        value={**original,'workspace_ids':original['workspace_ids']*2}
        with self.assertRaises(ContractError):validate('operations-request',value)

    def test_terminal_newlines_fail_all_identity_digest_version_boundaries(self):
        paths=[('operations-request','site_id'),('operations-request','plugin_id'),('operations-request','artifact_version'),('operations-request','artifact_digest'),
               ('operations-request-submit','operation_id'),('operations-request-submit','plan_hash'),('plan','operation_id'),('plan','base_release_digest'),
               ('binding','binding_id'),('endpoint','endpoint_config'),('worker-claims','workspace_id')]
        for fixture,field in paths:
            with self.subTest(fixture=fixture,field=field):
                value=example(fixture);value[field]+='\n'
                with self.assertRaises(ContractError):validate('operations-request' if fixture.startswith('operations-request') else fixture,value)
        value=example('manifest-native');value['permissions']['defines']['new.action\n']='invalid';
        with self.assertRaises(ContractError):validate('manifest',value)

    def test_prepared_hash_and_exact_transitive_targets_cannot_diverge(self):
        original=example('operations-view')
        for changed in ({'plan_hash':'sha256:'+'0'*64},{'operation_id':'00000000-0000-4000-8000-000000000999'},
                        {'targets':[{**original['targets'][0],'plugin_id':'org.example.other'}]},
                        {'targets':original['targets']*2},{'native_trusted_code':False},{'restart_required':False}):
            with self.subTest(changed=changed),self.assertRaises(ContractError):validate_operations_view({**original,**changed})

    def test_app_request_cannot_claim_approval_and_dimensions_remain_distinct(self):
        value=example('operations-view-status');value['state']='approved';value['approval_expires_at']='2026-10-28T06:15:00Z'
        with self.assertRaises(ContractError):validate_operations_view(value)
        value['source']='operator_journal_mirror';validate_operations_view(value)
        value['state']='completed'
        with self.assertRaises(ContractError):validate_operations_view(value)
        value['phase']='completed';validate_operations_view(value)

    def test_external_metadata_preview_requires_host_restart_without_native_trust(self):
        value=example('operations-view')
        for artifact in value['plan']['artifacts']:
            artifact.update(runtime='external_service',native_addon=None,migration_digests=[])
        value['native_trusted_code']=False;value['plan_hash']=plan_hash(value['plan'])
        validate_operations_view(value)
        value['restart_required']=False
        with self.assertRaises(ContractError):validate_operations_view(value)

    def test_checkpointed_native_feature_preview_differs_from_retained_short_profile(self):
        for backup in (False,True):
            value=example('operations-view');value['plan']['operation_type']='suspend'
            for artifact in value['plan']['artifacts']:artifact['action']='suspend'
            for target in value['targets']:target['action']='suspend'
            value['plan']['backup']['required']=backup;value['restart_required']=backup
            value['plan_hash']=plan_hash(value['plan']);validate_operations_view(value)
            value['restart_required']=not backup
            with self.assertRaises(ContractError):validate_operations_view(value)
    def test_dimensions_and_catalog_claims_remain_bounded(self):
        value=example('operations-view-status')
        value['dimensions'][0]['feature_state']='unloaded'
        with self.assertRaises(ContractError):validate_operations_view(value)
        metadata=example('manifest-native')['plugin']
        item={'plugin_id':metadata['id'],'version':metadata['version'],'artifact_digest':'sha256:'+'d'*64,
              'name':'N'*512,'description':metadata['description'],'publisher':'P'*512,'license':'L'*512,
              'runtime':'native','trust_model':'unsigned-development','signature_verified':False,
              'warnings':['Unsigned development artifact'],'policy_generation':1}
        catalog={'schema_version':1,'kind':'catalog','snapshot_digest':'sha256:'+'c'*64,'observed_at':'2026-10-28T06:00:00Z',
                 'stale':False,'items':[item],'next_offset':None}
        validate_operations_view(catalog)
        item['warnings']=[]
        with self.assertRaises(ContractError):validate_operations_view(catalog)
        item['warnings']=['Unsigned development artifact'];item['signature_verified']=True
        with self.assertRaises(ContractError):validate_operations_view(catalog)


if __name__=='__main__':unittest.main()
