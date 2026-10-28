"""G2 semantic/golden compatibility fixtures; later gates test real effects."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.contracts import (CONTRACTS, ContractError, api_range, canonical_plan, checked_path,
    load_json, native_version, normalize_manifest, package_version, plan_hash, validate, validate_binding, check_start_approval, resolve_ui)
from modular_platform.tokens import AUDIENCE, ISSUER, verify_worker_token
from jsonschema import Draft202012Validator
from packaging.version import Version
import jwt
import rfc8785
from cryptography.hazmat.primitives.asymmetric import rsa

EXAMPLES = ROOT / 'packages/contracts/examples/v1'


def example(name):
    return json.loads((EXAMPLES / (name + '.json')).read_text())


class Contracts(unittest.TestCase):
    def test_schema_dialect_and_examples(self):
        for path in CONTRACTS.glob('*.schema.json'):
            schema = json.loads(path.read_text())
            Draft202012Validator.check_schema(schema)
            self.assertEqual(schema['$schema'], 'https://json-schema.org/draft/2020-12/schema')
        for path in EXAMPLES.glob('*.json'):
            if path.name == 'plan.canonical.json': continue
            if path.stem in ['board','document-v2']:
                schema,definition=('boards','board') if path.stem=='board' else ('documents-v2','document')
                Draft202012Validator(json.loads((CONTRACTS/(schema+'.schema.json')).read_text())['$defs'][definition],format_checker=__import__('modular_platform.contracts',fromlist=['FORMAT_CHECKER']).FORMAT_CHECKER).validate(json.loads(path.read_text()))
                continue
            name = 'manifest' if path.stem.startswith('manifest-') else path.stem
            validate(name, json.loads(path.read_text()))

    def test_authoring_is_data_not_import(self):
        self.assertEqual(normalize_manifest(example('manifest-native'))['runtime']['addon_name'], 'mp_example_notes')
        text = '''schema_version=1
[plugin]
id='org.example.notes'
version='0.1.0'
'''
        with self.assertRaises(ContractError): normalize_manifest(text)
        # Handler module is deliberately absent in this interpreter. Validation
        # above succeeded without importing it or any Odoo package.
        self.assertNotIn('mp_example_notes', sys.modules)
        self.assertNotIn('odoo', sys.modules)

    def test_unknown_sensitive_keys_and_unsupported_majors(self):
        for name in ['sudo','site_id','installer_command','approved','docker_socket']:
            value=example('manifest-native'); value[name]=True
            with self.assertRaises(ContractError): normalize_manifest(value)
        for field in ['host_api_major','ui_api_major']:
            value=example('manifest-native');value['compatibility'][field]=2
            with self.assertRaises(ContractError):normalize_manifest(value)
        with self.assertRaises(ContractError):load_json('{"a":1,"a":2}')
        with self.assertRaises(ContractError):load_json('{"value":NaN}')

    def test_version_spelling_and_native_order(self):
        for invalid in ['v1.0.0','1.0','01.0.0','1.0.0rc1','1.0.0.post1','1!1.0.0','1.0.0+build','-1.0.0','1.0.0\n']:
            with self.subTest(version=invalid),self.assertRaises(ContractError):package_version(invalid)
        versions=['0.1.0','0.1.9','0.1.10','0.2.0','0.3.0','2.10.3']
        self.assertEqual(sorted(versions,key=package_version),versions)
        self.assertEqual(sorted(map(native_version,versions),key=Version),list(map(native_version,versions)))

    def test_migration_path_and_nonincreasing_transition(self):
        value=example('manifest-native')
        transition={'from':'0.1.0','to':'0.3.0','scripts':[{'path':'migrations/19.0.0.3.0/pre-transform.py','digest':'sha256:'+'a'*64,'phase':'pre'}],'preconditions':[],'postconditions':[],'retry':'reconcile','recovery':'restore_checkpoint'}
        value['upgrade']['transitions']=[transition]
        normalize_manifest(value)
        for path in ['migrations/0.0.0/pre-transform.py','../pre-transform.py','migrations/0.3.0/pre-transform.py']:
            other=copy.deepcopy(value);other['upgrade']['transitions'][0]['scripts'][0]['path']=path
            with self.assertRaises(ContractError):normalize_manifest(other)
        transition['to']='0.1.0'
        with self.assertRaises(ContractError):normalize_manifest(value)

    def test_alias_exact_version_provider_and_major(self):
        manifest=example('manifest-native');requirement=manifest['services']['requires'][0];provider={**manifest['services']['provides'][0],'plugin_id':'org.example.notes','installation_id':example('binding')['provider_installation_id']}
        binding=example('binding');validate_binding(binding,requirement,provider)
        for field,value in [('contract_major',2),('api_version','1.1'),('alias','other'),('service_id','org.example.other.documents'),('provider_plugin_id','org.example.other'),('provider_installation_id',binding['site_id'])]:
            other=copy.deepcopy(binding);other[field]=value
            with self.assertRaises(ContractError):validate_binding(other,requirement,provider)
        for spec in ['>=1.0','>=1.0,<3.0','^1.0','>=0.9,<2.0']:
            with self.assertRaises(ContractError):api_range(spec,1)
        self.assertIn(Version('1.4'),api_range('>=1.0,<2.0',1))
        manifest['services']['requires']*=2
        with self.assertRaises(ContractError):normalize_manifest(manifest)

    def test_parallel_contract_majors_are_explicit(self):
        manifest=example('manifest-native');one=manifest['services']['provides'][0];two={**one,'api_version':'2.0'}
        manifest['services']['provides'].append(two)
        manifest['services']['requires'].append({'alias':'documents_v2','id':one['id'],'contract_major':2,'version':'>=2.0,<3.0'})
        normalize_manifest(manifest)
        binding={**example('binding'),'alias':'documents_v2','api_version':'2.0','contract_major':2}
        two={**two,'plugin_id':'org.example.notes','installation_id':binding['provider_installation_id']}
        validate_binding(binding,manifest['services']['requires'][1],two)
        with self.assertRaises(ContractError):validate_binding(binding,manifest['services']['requires'][0],two)

    def test_remote_metadata_cannot_deploy_or_register_native_code(self):
        manifest=example('manifest-external');normalize_manifest(manifest)
        for target,key,value in [('runtime','addon_name','evil'),('external_service','url','http://attacker'),('external_service','command','run')]:
            other=copy.deepcopy(manifest);other[target][key]=value
            with self.assertRaises(ContractError):normalize_manifest(other)
        for target,key,value in [('data','models',['evil.model']),('ui','mode','trusted')]:
            other=copy.deepcopy(manifest);other[target][key]=value
            with self.assertRaises(ContractError):normalize_manifest(other)
        other=copy.deepcopy(manifest);other['services']['provides'][0]['handler']='evil:run'
        with self.assertRaises(ContractError):normalize_manifest(other)

    def test_plan_golden_bytes_hash_and_independent_js(self):
        plan=example('plan');gold=(EXAMPLES/'plan.canonical.json').read_bytes()
        self.assertEqual(canonical_plan(plan),gold)
        self.assertEqual(plan_hash(plan),(EXAMPLES/'plan.sha256').read_text().strip())
        # Independent ECMAScript encoding agrees for this ASCII-key, integer-only
        # plan; RFC sample below additionally exercises numeric/Unicode behavior.
        script="const fs=require('fs');let p=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));function c(v){return Array.isArray(v)?v.map(c):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,c(v[k])])):v;}process.stdout.write(JSON.stringify(c(p)));"
        self.assertEqual(subprocess.check_output(['node','-e',script,str(EXAMPLES/'plan.json')]),gold)
        for field in ['base_state_digest','target_release_digest']:
            changed=copy.deepcopy(plan);changed[field]='sha256:'+'0'*64
            self.assertNotEqual(plan_hash(changed),plan_hash(plan))
        for field,value in [('approved',True),('shell','echo hi'),('plan_hash','sha256:'+'0'*64)]:
            changed=copy.deepcopy(plan);changed[field]=value
            with self.assertRaises(ContractError):plan_hash(changed)
        changed=copy.deepcopy(plan);changed['policy_version']=1.0
        with self.assertRaises(ContractError):plan_hash(changed)

    def test_rfc8785_library_vector(self):
        self.assertEqual(rfc8785.dumps({'b':1e30,'a':[4.50,2e-3,'€']}),b'{"a":[4.5,0.002,"\xe2\x82\xac"],"b":1e+30}')

    def test_approval_exact_target_expiry_revocation_and_consumption(self):
        plan=example('plan');approval=example('approval');now=datetime(2026,10,28,0,5,tzinfo=timezone.utc)
        check_start_approval(plan,approval,operator_generation=1,now=now)
        for field,value in [('state','revoked'),('state','consumed'),('expires_at','2026-10-28T00:02:00Z'),('operation_id',plan['deployment_id']),('consumed_operation_id',plan['operation_id'])]:
            changed={**approval,field:value}
            with self.assertRaises(ContractError):check_start_approval(plan,changed,operator_generation=1,now=now)
        with self.assertRaises(ContractError):check_start_approval(plan,approval,operator_generation=2,now=now)

    def test_utc_calendar_validation_does_not_depend_on_optional_formats(self):
        plan=example('plan')
        for timestamp in ['2026-99-28T00:00:00Z','2026-02-30T00:00:00Z','2026-10-28T25:00:00Z','2026-10-28T00:00:00+00:00']:
            with self.subTest(timestamp=timestamp),self.assertRaises(ContractError):validate('plan',{**plan,'created_at':timestamp})
        validate('plan',plan)
        roles=json.loads((CONTRACTS/'role-permissions.json').read_text())
        self.assertIn('org.modularplatform.identity:workspace.members.manage',roles['plugin_permissions']['org.example.notes']['administrator'])

    def test_actor_host_and_method_dtos_do_not_accept_privilege_claims(self):
        for schema in ['workspace-context','host-context','service-request']:
            value=example(schema);value['sudo']=True
            with self.assertRaises(ContractError):validate(schema,value)
        schema=json.loads((CONTRACTS/'documents.schema.json').read_text())['$defs']['update_input']
        validator=Draft202012Validator(schema)
        self.assertTrue(validator.is_valid({'note_id':example('notes-export')['notes'][0]['id'],'expected_revision':1,'title':'Changed'}))
        self.assertFalse(validator.is_valid({'note_id':'1','workspace_id':'other','expected_revision':1}))

    def test_retired_jwt_vector_signature_and_expiry(self):
        token=(EXAMPLES/'worker-token.txt').read_text().strip();key=(EXAMPLES/'worker-public.pem').read_bytes()
        claims=jwt.decode(token,key,algorithms=['RS256'],issuer=ISSUER,audience=AUDIENCE,options={'verify_exp':False})
        self.assertEqual(claims,example('worker-claims'))
        with self.assertRaises(jwt.ExpiredSignatureError):verify_worker_token(token,key,key_id='retired-contract-fixture',request=example('worker-request'))

    def test_live_jwt_scope_audience_algorithm_and_lifetime(self):
        private=rsa.generate_private_key(public_exponent=65537,key_size=2048);public=private.public_key()
        claims=example('worker-claims');now=int(time.time());claims.update(iat=now,nbf=now,exp=now+120)
        def sign(value):return jwt.encode(value,private,algorithm='RS256',headers={'kid':'test'})
        request=example('worker-request')
        verify_worker_token(sign(claims),public,key_id='test',request=request)
        for field,value in [('aud','mp-host-v1'),('workspace_id',example('binding')['site_id']),('exp',now+301),('methods',[])]:
            changed={**claims,field:value}
            with self.assertRaises((ContractError,jwt.PyJWTError)):verify_worker_token(sign(changed),public,key_id='test',request=request)
        with self.assertRaises((ContractError,jwt.PyJWTError)):verify_worker_token(jwt.encode(claims,'fixture-key-'*4,algorithm='HS256'),public,key_id='test',request=request)
        with self.assertRaises(ContractError):verify_worker_token(sign(claims),public,key_id='untrusted',request=request)

    def test_paths_cannot_escape_package(self):
        for invalid in ['../escape','a/../b','C:/escape','/absolute','a\\b','a//b','./a']:
            with self.assertRaises(ContractError):checked_path(invalid)
        self.assertEqual(checked_path('schemas/notes.json'),'schemas/notes.json')

    def test_workspace_admin_inputs_cannot_name_a_site_or_installation(self):
        member=example('workspace-membership');settings=example('workspace-settings')
        validate('workspace-membership',member);validate('workspace-settings',settings)
        for key in ['workspace_id','site_id','user_id','sudo','installation_id','command']:
            with self.subTest(key=key),self.assertRaises(ContractError):validate('workspace-membership',{**member,key:'forged'})
            with self.subTest(key=key),self.assertRaises(ContractError):validate('workspace-settings',{**settings,key:'forged'})
        with self.assertRaises(ContractError):validate('workspace-membership',{**member,'role':'site_operator'})

    def test_composed_ui_dependency_ownership_order_and_compatibility(self):
        manifests=[example(name) for name in ['manifest-notes-composed','manifest-labels','manifest-canvas']]
        registry=resolve_ui(manifests)
        self.assertEqual(len(registry['contributions']),1)
        self.assertEqual(registry['contributions'][0]['plugin_id'],'org.example.notes_labels')
        self.assertIn('org.example.notes:slot:detail_actions',registry['slots'])
        for mutation in ['major','dependency','duplicate','cycle','ownership','path']:
            changed=copy.deepcopy(manifests);label=changed[1];item=label['ui']['contributions'][0]
            if mutation=='major':item['slot_major']=2
            if mutation=='dependency':label['dependencies']['plugins']={}
            if mutation=='duplicate':label['ui']['contributions'].append(copy.deepcopy(item))
            if mutation=='ownership':item['id']='org.example.notes:action:forged'
            if mutation=='path':label['ui']['commands'][0]['input_schema']='../escape'
            if mutation=='cycle':
                other={**item,'id':'org.example.notes_labels:action:second','after':[item['id']]};item['after']=[other['id']];label['ui']['contributions'].append(other)
            with self.subTest(mutation=mutation),self.assertRaises(ContractError):resolve_ui(changed)
        optional=copy.deepcopy(manifests);item=optional[1]['ui']['contributions'][0];item.update(slot_major=2,optional=True)
        self.assertEqual(resolve_ui(optional)['contributions'],[])
        self.assertEqual(resolve_ui([manifests[0]])['contributions'],[])

    def test_board_and_documents_v2_dtos_cannot_expand_authority(self):
        for name,definition,example_name in [('boards','board','board'),('documents-v2','document','document-v2')]:
            validator=Draft202012Validator(json.loads((CONTRACTS/(name+'.schema.json')).read_text())['$defs'][definition])
            value=example(example_name);self.assertTrue(validator.is_valid(value))
            for key in ['workspace_id','sudo','user_id','database']:
                self.assertFalse(validator.is_valid({**value,key:'forged'}))
        get=Draft202012Validator(json.loads((CONTRACTS/'documents-v2.schema.json').read_text())['$defs']['get_input'])
        self.assertFalse(get.is_valid({'note_id':example('document-v2')['document_id']}))
        self.assertTrue(get.is_valid({'document_id':example('document-v2')['document_id']}))


if __name__ == '__main__': unittest.main()
