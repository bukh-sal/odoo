"""Inert metadata history must not become executable source or live authority."""
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));sys.path.insert(0,str(ROOT/'tests'))
from modular_platform.projection import project_deployment
from modular_platform.resolution import PlanningError
from test_release_staging import staged_runtime
from test_resolution import plugin
from test_plans import ident,STAMP,binding,target


class TombstoneProjection(unittest.TestCase):
    def setUp(self):
        self.active=plugin('a');self.saved=plugin('b','1.0.0',depends={'a':'>=1'});self.current=plugin('b','2.0.0',depends={'a':'>=1'})
        self.catalog=[self.active,self.saved,self.current]
        self.config=dict(deployment_id=ident(10),generation=3,release_created_at=STAMP,policy_version=1,operator_authorization_generation=1)
        self.site=dict(site_id=ident(20),installations=[dict(installation_id=ident(100),plugin_id='org.test.a',version='1.0.0',digest=self.active['digest'],runtime='native',metadata_state='installed',manifest=self.active['manifest']),
            dict(installation_id=ident(101),plugin_id='org.test.b',version='1.0.0',digest=self.saved['digest'],runtime='native',metadata_state='removed',manifest=self.saved['manifest'])],
            features=[dict(installation_id=ident(100),plugin_id='org.test.a',workspace_id=ident(30),feature_state='enabled'),
                      dict(installation_id=ident(101),plugin_id='org.test.b',workspace_id=ident(30),feature_state='suspended')],
            native_modules=[dict(addon='test_a',state='installed',version='19.0.1.0.0')],bindings=[],grants=[],workspaces=[],memberships=[])

    def project(self,present=True):
        runtime=staged_runtime([self.active,self.current] if present else [self.active])
        return project_deployment(self.config,dict(image_id='sha256:'+'a'*64,runtime=runtime,sites=[self.site]),self.catalog)['state']

    def test_old_uninstalled_manifest_is_history_when_a_newer_source_is_present(self):
        state=self.project()
        self.assertEqual([p['version'] for p in state['release_lock']['plugins'] if p['plugin_id']=='org.test.b'],['2.0.0'])
        row=next(r for r in state['installations'] if r['plugin_id']=='org.test.b')
        self.assertEqual((row['installation_id'],row['state'],row['metadata_state'],row['feature_state']),
                         (ident(101),'not_installed','removed','suspended'))

    def test_package_absence_does_not_drop_or_promote_its_tombstone(self):
        self.catalog=[self.active]  # No current trust/archive claim for saved data.
        state=self.project(present=False)
        self.assertEqual([p['plugin_id'] for p in state['release_lock']['plugins']],['org.test.a'])
        self.assertEqual(len(state['installations']),2)
        self.assertEqual(next(r for r in state['installations'] if r['plugin_id']=='org.test.b')['state'],'not_installed')

    def test_active_authority_or_native_state_cannot_hide_behind_removed_metadata(self):
        original=copy.deepcopy(self.site)
        for mutation in ('availability','grant','native','binding','ownership','active_without_source'):
            self.site=copy.deepcopy(original)
            if mutation=='availability':self.site['features'][1]['feature_state']='enabled'
            elif mutation=='grant':self.site['grants']=[dict(installation_id=ident(101),workspace_id=ident(30),capability='org.test.b:read',state='approved')]
            elif mutation=='native':self.site['native_modules'].append(dict(addon='test_b',state='installed',version='19.0.1.0.0'))
            elif mutation=='binding':self.site['bindings']=[dict(descriptor=binding(target(value=101,name='b'),target(value=100,name='a')),state='active')]
            elif mutation=='ownership':self.site['features'][1]['plugin_id']='org.test.a'
            else:self.site['installations'][1]['metadata_state']='installed'
            with self.subTest(mutation=mutation),self.assertRaises(PlanningError):self.project(present=False)


if __name__=='__main__':unittest.main()
