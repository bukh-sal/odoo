"""Required manager behavior with real archive bytes, not a second parser."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tools'))
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.contracts import ContractError,normalize_manifest
from modular_platform.manager_views import details_view,installed_view,validate_upload,page_offset
from reference_package import assemble
from test_artifacts import pack

NOW='2026-10-28T22:10:00Z';WORKSPACE='00000000-0000-4000-8000-000000000002'
INSTALL='00000000-0000-4000-8000-000000000001'
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()

class ManagerViews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest,cls.raw,cls.payload=assemble(ROOT,'plugins/notes/plugin.toml')
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'source.mplug';path.write_bytes(cls.raw)
            cls.descriptor=ArtifactValidator(TrustPolicy('curated',frozenset([digest(cls.raw)]),generation=3)).verify(path).descriptor()

    def setUp(self):
        self.profile={'catalog':[copy.deepcopy(self.descriptor)],'observed_at':NOW}
        row={'installation_id':INSTALL,'plugin_id':'org.example.notes','version':self.manifest['plugin']['version'],
             'digest':digest(self.raw),'runtime':'native','metadata_state':'installed','manifest':self.manifest}
        bindings=[]
        for requirement in self.manifest['services']['requires']:
            provide=next(p for p in self.manifest['services']['provides'] if p['id']==requirement['id'] and int(p['api_version'].split('.')[0])==requirement['contract_major'])
            bindings.append({'state':'active','descriptor':{'consumer_installation_id':INSTALL,'provider_installation_id':INSTALL,
                'provider_plugin_id':'org.example.notes','workspace_id':WORKSPACE,'alias':requirement['alias'],
                'service_id':requirement['id'],'contract_major':requirement['contract_major'],'api_version':provide['api_version']}})
        self.metadata={'installations':[row],'features':[{'installation_id':INSTALL,'workspace_id':WORKSPACE,'feature_state':'enabled'}],
            'native_modules':[{'addon':'mp_example_notes','version':'19.0.'+self.manifest['plugin']['version'],'state':'installed'}],'bindings':bindings}

    def test_real_verified_upload_extracts_and_cleans_without_imports(self):
        with tempfile.TemporaryDirectory() as name:
            result=validate_upload(self.raw,digest(self.raw),self.profile,now=NOW,parent=name)
            self.assertEqual(result['result'],'verified');self.assertEqual(list(Path(name).iterdir()),[])
        self.assertFalse(result['retained']);self.assertFalse(result['executed']);self.assertNotIn('odoo',sys.modules)
        self.assertNotIn('mp_example_notes',sys.modules)

    def test_unapproved_bytes_stop_at_trust_and_digest_mismatch_is_distinct(self):
        self.assertEqual(validate_upload(b'not a zip',digest(b'not a zip'),self.profile,now=NOW)['validation_scope'],'trust_gate')
        result=validate_upload(self.raw,'sha256:'+'0'*64,self.profile,now=NOW)
        self.assertEqual(result['error_code'],'DIGEST_MISMATCH');self.assertIsNone(result['artifact'])

    def test_hostile_curated_archive_uses_shared_validator_and_cleans(self):
        raw=pack(self.payload,extras=[('../escape.txt',b'no')]);self.profile['catalog'][0]['digest']=digest(raw)
        with tempfile.TemporaryDirectory() as name:
            value=validate_upload(raw,digest(raw),self.profile,now=NOW,parent=name)
            self.assertEqual(value['error_code'],'INVALID_ARCHIVE');self.assertEqual(list(Path(name).iterdir()),[])

    def test_size_identity_and_pagination_reject_before_processing(self):
        for value in ('-1','1.0','1\n','10001','\u0661'):
            with self.assertRaises(ContractError):page_offset(value)
        with patch('modular_platform.manager_views.UPLOAD_LIMIT',8),self.assertRaises(ContractError):validate_upload(b'x'*9,digest(b'x'*9),self.profile,now=NOW)
        with self.assertRaises(ContractError):validate_upload(b'',digest(b''),self.profile,now=NOW)
        with self.assertRaises(ContractError):validate_upload(self.raw,digest(self.raw)+'\n',self.profile,now=NOW)

    def test_details_exact_provenance_full_declarations_and_staleness(self):
        value=details_view(self.profile,digest(self.raw),now='2026-10-28T23:10:00Z')
        self.assertTrue(value['stale']);self.assertEqual(value['manifest'],self.manifest)
        self.assertEqual(value['provenance']['source_files_count'],len(self.descriptor['provenance']['source_files']))
        self.assertFalse(value['provenance']['publisher_identity_verified']);self.assertFalse(value['feature_suspension_unloads_code'])
        self.assertIsNone(details_view(self.profile,'sha256:'+'0'*64,now=NOW))

    def test_installed_health_does_not_infer_plugin_liveness(self):
        value=installed_view(self.profile,self.metadata,now=NOW)['items'][0]
        self.assertEqual(value['database_state'],'installed');self.assertEqual(value['health']['state'],'unknown')
        self.assertEqual(value['dependencies']['state'],'satisfied');self.assertEqual(value['features'][0]['availability'],'enabled')
        self.metadata['native_modules'][0]['version']='19.0.0.0.0'
        value=installed_view(self.profile,self.metadata,now=NOW)['items'][0]
        self.assertEqual(value['database_state'],'failed');self.assertEqual(value['health']['state'],'degraded')

    def test_required_binding_and_workspace_availability_are_observed(self):
        self.metadata['bindings']=[]
        value=installed_view(self.profile,self.metadata,now=NOW)['items'][0]
        self.assertEqual(value['dependencies']['state'],'unavailable');self.assertTrue(value['dependencies']['issues'])
        self.assertEqual(value['health']['state'],'degraded')

    def test_enabled_canvas_detects_suspended_notes_provider_without_expanding_canvas(self):
        manifest,raw,_=assemble(ROOT,'plugins/canvas/plugin.toml');canvas='00000000-0000-4000-8000-000000000003'
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'canvas.mplug';path.write_bytes(raw)
            descriptor=ArtifactValidator(TrustPolicy('curated',frozenset([digest(raw)]),generation=3)).verify(path).descriptor()
        self.profile['catalog'].append(descriptor)
        self.metadata['installations'].append({'installation_id':canvas,'plugin_id':'org.example.canvas','version':manifest['plugin']['version'],
            'digest':digest(raw),'runtime':'native','metadata_state':'installed','manifest':manifest})
        self.metadata['native_modules'].append({'addon':'mp_example_canvas','version':'19.0.'+manifest['plugin']['version'],'state':'installed'})
        self.metadata['features'].append({'installation_id':canvas,'workspace_id':WORKSPACE,'feature_state':'enabled'})
        for requirement in manifest['services']['requires']:
            provider=INSTALL if requirement['id'].startswith('org.example.notes.') else canvas
            plugin='org.example.notes' if provider==INSTALL else 'org.example.canvas'
            self.metadata['bindings'].append({'state':'active','descriptor':{'consumer_installation_id':canvas,'provider_installation_id':provider,
                'provider_plugin_id':plugin,'workspace_id':WORKSPACE,'alias':requirement['alias'],'service_id':requirement['id'],
                'contract_major':requirement['contract_major'],'api_version':str(requirement['contract_major'])+'.0'}})
        value=next(r for r in installed_view(self.profile,self.metadata,now=NOW)['items'] if r['installation_id']==canvas)
        self.assertEqual(value['dependencies']['state'],'satisfied')
        self.metadata['features'][0]['feature_state']='suspended'
        value=next(r for r in installed_view(self.profile,self.metadata,now=NOW)['items'] if r['installation_id']==canvas)
        self.assertEqual(value['dependencies']['state'],'unavailable');self.assertEqual(value['health']['state'],'degraded')

    def test_removed_metadata_does_not_claim_native_schema_unloaded(self):
        self.metadata['installations'][0]['metadata_state']='removed'
        value=installed_view(self.profile,self.metadata,now=NOW)['items'][0]
        self.assertEqual(value['database_state'],'installed');self.assertEqual(value['health']['state'],'degraded')

    def test_inert_removed_history_does_not_require_a_current_archive_or_live_bindings(self):
        self.metadata['installations'][0]['metadata_state']='removed'
        self.metadata['features'][0]['feature_state']='suspended'
        self.metadata['native_modules']=[];self.metadata['bindings']=[];self.profile['catalog']=[]
        row=installed_view(self.profile,self.metadata,now=NOW)['items'][0]
        self.assertEqual(row['database_state'],'not_installed');self.assertEqual(row['health']['state'],'unknown')
        self.assertEqual(row['dependencies']['state'],'unknown');self.assertIsNone(row['artifact'])

    def test_missing_catalog_metadata_never_claims_verified_health(self):
        self.profile['catalog']=[]
        value=installed_view(self.profile,self.metadata,now=NOW)['items'][0]
        self.assertEqual(value['database_state'],'failed');self.assertIsNone(value['artifact'])
        self.assertEqual(value['dependencies']['state'],'unknown')

if __name__=='__main__':unittest.main()
