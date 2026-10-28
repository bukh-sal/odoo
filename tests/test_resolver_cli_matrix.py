"""Required resolver failures/successes through the actual immutable catalog CLI."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.contracts import native_version
from modular_platform.plans import check_bundle
from test_artifacts import inventory,pack,toml
from test_resolution import plugin,wheel,provide,require,ENVIRONMENT
from test_plans import base_state,ident,PROVENANCE,STAMP

def archive(candidate):
    manifest=candidate['manifest'];addon=manifest['runtime']['addon_name'];prefix='backend/odoo_addons/'+addon+'/'
    native={**candidate['native_manifest'],'version':native_version(manifest['plugin']['version']),'license':'LGPL-3'}
    files={'plugin.toml':toml(manifest),prefix+'__manifest__.py':repr(native).encode(),
           prefix+'__init__.py':b'raise RuntimeError("PLANNING MUST NEVER IMPORT THIS FIXTURE")\n',
           'notices/LICENSE':b'Synthetic qualification fixture; never installed.\n'}
    for service in manifest['services']['provides']:
        files[service['schema']]=b'{"type":"object"}'
        files[prefix+'services.py']=b'raise RuntimeError("PLANNING MUST NEVER IMPORT SERVICE CODE")\n'
    return pack(inventory(files),root=manifest['plugin']['id'])

class ResolverCLI(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.folder=Path(self.temporary.name)
        self.store=self.folder/'catalog';self.config=self.folder/'operator.json';self.input=self.folder/'input.json'

    def curate(self,candidates):
        raw=[archive(c) for c in candidates];digests=['sha256:'+hashlib.sha256(b).hexdigest() for b in raw]
        self.config.write_text(json.dumps({'schema_version':1,'mode':'curated','approved_digests':digests,'allow_unsigned_development':False,'generation':1}),encoding='utf-8')
        catalog=Catalog(self.store,ArtifactValidator(TrustPolicy(approved_digests=frozenset(digests))));descriptors=[]
        for n,(data,digest) in enumerate(zip(raw,digests)):
            path=self.folder/(str(n)+'.mplug');path.write_bytes(data);descriptors.append(catalog.add(path,expected_digest=digest))
        return descriptors

    def invoke(self,requested,targets,*,state=None,python=(),choices=()):
        document={'state':copy.deepcopy(state or base_state()),'environment':ENVIRONMENT,'provenance':PROVENANCE,'python_metadata':list(python),
            'request':{'operation_type':'install','requested':{'org.test.'+k:v for k,v in requested.items()},'targets':[
                {'installation_id':ident(100+i),'site_id':ident(20),'workspace_id':ident(30),'plugin_id':'org.test.'+name,'action':'install'} for i,name in enumerate(targets)],
                'provider_choices':list(choices),'operation_id':ident(501),'created_at':STAMP}}
        self.input.write_text(json.dumps(document),encoding='utf-8')
        def fingerprint():return {p.relative_to(self.store).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.store.rglob('*') if p.is_file()}
        before=fingerprint();config_before=self.config.read_bytes()
        result=subprocess.run([sys.executable,str(ROOT/'tools/modular.py'),'--config',str(self.config),'plugin','plan','--input',str(self.input),'--store',str(self.store)],capture_output=True,text=True,timeout=60)
        self.assertEqual(before,fingerprint());self.assertEqual(config_before,self.config.read_bytes())
        if result.returncode:
            self.assertEqual(result.returncode,2);error=json.loads(result.stderr);self.assertEqual(error['error'],'VALIDATION_FAILED');self.assertNotIn('PLANNING MUST NEVER IMPORT',result.stderr)
            return error['message']
        bundle=json.loads(result.stdout);self.assertTrue(check_bundle(bundle,document['state']));return bundle

    def test_missing_transitive_dependency_fails_before_any_mutation(self):
        self.curate([plugin('a',depends={'b':'>=1'}),plugin('b',depends={'c':'>=2'})])
        message=self.invoke({'a':''},['a','b']);self.assertIn('org.test.c>=2',message);self.assertIn('plugin:org.test.b',message)

    def test_version_conflict_explains_both_incompatible_constraints(self):
        self.curate([plugin('a',depends={'shared':'<2'}),plugin('b',depends={'shared':'>=2'}),plugin('shared'),plugin('shared','2.0.0')])
        message=self.invoke({'a':'','b':''},['a','b','shared']);self.assertIn('org.test.shared<2',message);self.assertIn('org.test.shared>=2',message)

    def test_cycle_reports_the_complete_hard_dependency_cycle(self):
        self.curate([plugin('a',depends={'b':''}),plugin('b',depends={'c':''}),plugin('c',depends={'a':''})])
        message=self.invoke({'a':''},['a','b','c']);self.assertIn('org.test.a -> org.test.b -> org.test.c -> org.test.a',message)

    def test_python_conflict_is_distinct_and_explains_both_constraints(self):
        self.curate([plugin('a',python=['shared<2']),plugin('b',python=['shared>=2'])])
        message=self.invoke({'a':'','b':''},['a','b'],python=[wheel('shared'),wheel('shared','2.0')])
        self.assertIn('Python dependency conflict',message);self.assertIn('python:shared<2',message);self.assertIn('python:shared>=2',message)

    def test_ambiguous_provider_rejects_then_explicit_binding_selects_only_one(self):
        self.curate([plugin('consumer',requires=[require()]),plugin('one',provides=[provide('one')]),plugin('two',provides=[provide('two')])])
        message=self.invoke({'consumer':''},['consumer','two']);self.assertIn('Explicit provider binding',message);self.assertIn('org.test.one',message);self.assertIn('org.test.two',message)
        bundle=self.invoke({'consumer':''},['consumer','two'],choices=[{'consumer':'org.test.consumer','alias':'documents','provider':'org.test.two'}])
        self.assertEqual({b['provider_plugin_id'] for b in bundle['operation_lock']['bindings']},{'org.test.two'})
        self.assertEqual({p['plugin_id'] for p in bundle['operation_lock']['release']['plugins']},{'org.test.consumer','org.test.two'})

    def test_optional_absent_and_incompatible_leave_base_plan_valid(self):
        self.curate([plugin('consumer',optional={'one':'>=2'},requires=[require(optional=True)]),plugin('one',provides=[provide('one')])])
        absent=self.invoke({'consumer':''},['consumer']);self.assertEqual(len(absent['operation_lock']['release']['plugins']),1)
        self.assertFalse(absent['operation_lock']['release']['optional_integrations'][0]['available']);self.assertEqual(absent['operation_lock']['bindings'],[])
        incompatible=self.invoke({'consumer':'','one':''},['consumer','one']);self.assertFalse(incompatible['operation_lock']['release']['optional_integrations'][0]['available'])

    def test_compatible_locked_dependency_is_preserved_when_another_plugin_installs(self):
        old,new,consumer=self.curate([plugin('a'),plugin('a','2.0.0'),plugin('consumer',depends={'a':'>=1'})])
        state=base_state([old]);bundle=self.invoke({'consumer':''},['consumer'],state=state)
        versions={p['plugin_id']:p['version'] for p in bundle['operation_lock']['release']['plugins']}
        self.assertEqual(versions,{'org.test.a':'1.0.0','org.test.consumer':'1.0.0'})

if __name__=='__main__':unittest.main()
