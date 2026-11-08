"""Independently reconstructed adoption plans, using real reviewed app bytes."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'tests')]
from application_package import assemble_application
from modular_platform.artifacts import ArtifactValidator,TrustPolicy
from modular_platform import tasks_adoption as ta
from modular_platform.plans import data_digest,release_lock,plan_hash,_display,check_bundle
from modular_platform.projection import runtime_inputs
from modular_platform.resolution import resolve_release,PlanningError
from modular_platform.operator_os import OperatorError
from modular_platform.release_staging import prepare_staged_plan
from modular_platform.native_executor import native_maintenance_flags
import test_release_staging as staged
from test_plans import ident,STAMP,PROVENANCE


class TasksAdoptionPlanning(unittest.TestCase):
    def setUp(self):
        fixture=staged.StagedPlans();fixture.setUp()
        self.old=fixture.old
        _,raw,_=assemble_application(ROOT,'plugins/aurora_tasks/application.toml')
        self.assertEqual('sha256:'+hashlib.sha256(raw).hexdigest(),ta.ARTIFACT)
        temporary=tempfile.TemporaryDirectory(prefix='mp-tasks-plan-');self.addCleanup(temporary.cleanup)
        archive=Path(temporary.name)/'tasks.mplug';archive.write_bytes(raw)
        self.app=ArtifactValidator(TrustPolicy(approved_digests=frozenset({ta.ARTIFACT}))).verify(archive).descriptor()
        self.catalog=[self.old,self.app]
        self.base=staged.staged_runtime([self.old]);self.runtime=staged.staged_runtime(self.catalog)
        for runtime,version in [(self.base,'0.1.47'),(self.runtime,'0.1.49')]:
            runtime['platform_version']=version
            runtime['inventory']['native_addons'].update(web=None,mp_aurora_tasks=None)
            runtime['native_manifests']={name:dict(version='19.0.1.0') for name in runtime['inventory']['native_addons']}
            runtime['native_manifests']['test_a']['version']='19.0.1.0.0'
            runtime['native_manifests']['mp_core']['version']='19.0.'+version
            runtime['native_manifests']['mp_aurora_tasks']=dict(version='19.0.0.1.0',depends=['web'])
        self.base['inventory_digest']=ta.SOURCE_INVENTORY
        self.runtime['inventory_digest']='sha256:'+'f'*64
        self.runtime['native_manifests']['mp_aurora_tasks']=copy.deepcopy(self.app['native_manifest'])
        old_name=self.runtime['inventory']['artifacts'][ta.APP]['file']
        new_name=ta.APP+'-'+ta.VERSION+'.mplug'
        self.runtime['inventory']['artifacts'][ta.APP]['file']=new_name
        self.runtime['inventory']['files'].pop('artifacts/'+old_name)
        self.runtime['inventory']['files']['artifacts/'+new_name]=ta.ARTIFACT[7:]
        self.runtime['inventory']['policy']['application_packages']=['plugins/aurora_tasks/application.toml']
        for path in [ta.RECIPE_PATH,ta.CHILD_PATH]:self.runtime['inventory']['files'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
        self.site=copy.deepcopy(fixture.site)
        self.site['native_modules']=sorted([dict(addon=n,state='installed',version=m['version']) for n,m in self.base['native_manifests'].items()],key=lambda r:r['addon'])
        _,environment,provenance=runtime_inputs(self.base,[self.old])
        resolved=resolve_release([self.old],[],environment,{'org.test.a':'==1.0.0'})
        lock=release_lock(resolved,provenance,generation=1,created_at=STAMP)
        state=copy.deepcopy(fixture.document['state']);state.update(release_lock=lock,release_digest=data_digest(lock))
        self.document=dict(state=state,environment=environment,provenance=provenance,python_metadata=[])
        self.document['state']['installations']=copy.deepcopy(fixture.document['state']['installations'])
        self.target=copy.deepcopy(fixture.target);self.target['action']='deploy'
        self.declaration=json.loads((ROOT/'packages/contracts/examples/v1/foundation-transition/tasks-adoption.json').read_bytes())
        d=self.declaration
        d['source']['policy_digest']=data_digest(self.base['inventory']['policy'])
        d['target'].update(inventory_digest=self.runtime['inventory_digest'],policy_digest=data_digest(self.runtime['inventory']['policy']),
            recipe_sha256=self.runtime['inventory']['files'][ta.RECIPE_PATH],child_sha256=self.runtime['inventory']['files'][ta.CHILD_PATH])
        d['source_changes']=ta.source_diff(self.base,self.runtime)
        d['site_effects'][0].update(site_id=self.site['site_id'],native_modules=copy.deepcopy(self.site['native_modules']))
        self.descriptor=dict(stage_digest='sha256:'+'c'*64,base_image_id=ta.SOURCE_IMAGE,
                             target_image_id=d['target']['image_id'],inventory_digest=self.runtime['inventory_digest'],runtime_digest=data_digest(self.runtime))

    def prepare(self,*,declaration=True,targets=None):
        if targets is None:targets=[self.target]+([ta.adoption_target(self.declaration)] if ta.adoption_target(self.declaration) else [])
        return prepare_staged_plan(self.document,[self.site],self.catalog,self.runtime,self.descriptor,
            targets=targets,operation_type='core_upgrade',operation_id=ident(500),created_at=STAMP,
            base_runtime=self.base,foundation_transition=self.declaration if declaration else None)

    def validator(self):
        result=staged.StagedPlans.validator(self)
        result.stage_store.load=lambda descriptor:(copy.deepcopy(self.descriptor),dict(runtime=copy.deepcopy(self.runtime),foundation_transition=copy.deepcopy(self.declaration)))
        return result

    def test_real_app_bytes_closed_native_adoption_and_independent_reconstruction(self):
        bundle=self.prepare()
        check_bundle(bundle,self.document['state'])
        self.assertEqual(self.validator()(bundle),self.document['state'])
        self.assertEqual(bundle['operation_lock']['native_site_scope_protocol'],1)
        self.assertTrue(bundle['plan']['destructive'])
        self.assertEqual(bundle['plan']['permission_changes'],[])
        self.assertEqual(native_maintenance_flags(bundle,{ta.APP:self.app}),['-u','mp_core,mp_aurora_tasks'])

    def test_missing_recipe_scope_and_rehashed_native_change_are_denied(self):
        with self.assertRaises((OperatorError,PlanningError)):self.prepare(declaration=False)
        with self.assertRaises((OperatorError,PlanningError)):self.prepare(targets=[self.target])
        bundle=self.prepare();bundle['operation_lock']['native_core_changes'][0]['target_version']='19.0.0.1.999'
        bundle['plan']['dependency_lock_digest']=data_digest(bundle['operation_lock']);bundle['plan_hash']=plan_hash(bundle['plan'])
        bundle['display']=_display(bundle['plan'],bundle['operation_lock'])
        with self.assertRaises(OperatorError):self.validator()(bundle)

    def test_same_available_app_does_not_install_it_when_native_source_absent(self):
        self.site['native_modules']=[r for r in self.site['native_modules'] if r['addon']!=ta.ADDON]
        self.declaration['site_effects'][0].update(native_modules=copy.deepcopy(self.site['native_modules']),tasks_installed=False,retained_tables=[],stage_additions=[])
        bundle=self.prepare()
        self.assertEqual(bundle['operation_lock']['targets'],[self.target])
        self.assertNotIn('native_site_scope_protocol',bundle['operation_lock'])
        self.assertEqual(native_maintenance_flags(bundle,{}),['-u','mp_core'])
        self.assertEqual(self.validator()(bundle),self.document['state'])


if __name__=='__main__':unittest.main()
