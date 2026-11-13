"""Actual completed journal/history and unchanged removal validators.

Only OS ACL, Docker/SQL and native external boundaries are simulated. Native
multi-source qualification is recorded separately from these host source tests.
"""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk'),str(ROOT)]
import test_completed_checkpoint_flow as fixture
from modular_platform import retained_recovery_inventory as module
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest


class RetainedRecoveryInventory(unittest.TestCase):
    def setUp(self):
        b=self.b=fixture.CompletedCheckpointFlow('test_actual_shared_resume_activates_inside_locks_and_preserves_completed_source')
        b.setUp();self.addCleanup(b.doCleanups)
        decision=b.restored();b.recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True)
        self.config=copy.deepcopy(b.native.config);self.source=b.config['sites'][0]['database']
        self.inventory=dict(databases=sorted([self.config['sites'][0]['database'],self.source,'postgres']),maintenance_relations=[])
        self.site=dict(site_id=fixture.SITE,release_digest=data_digest(b.config['published_release']),
            release_generation=str(b.config['published_release']['generation']),active_inventory_digest=fixture.INVENTORY,
            workspaces=[dict(workspace_id='A')],native_modules=[dict(addon='mp_core',state='installed')],
            installations=[dict(installation_id='installation',plugin_id='dev.local.documents',metadata_state='removed',manifest=dict(runtime=dict(addon_name='mp_documents')))],
            features=[dict(installation_id='installation',workspace_id='A',feature_state='suspended')],
            grants=[dict(installation_id='installation',state='revoked')],bindings=[])
        self.observation=dict(sites=[dict(site_id=fixture.SITE)],runtime=dict(inventory=dict(artifacts={'dev.local.documents':dict(addon='mp_documents')})))
        self.observer=SimpleNamespace(config=self.config,_container=lambda service:'db')
        self.worker=dict(Id='c'*64,Image=fixture.IMAGE,State=dict(Running=False,ExitCode=0),Config=dict(Labels={
            'com.docker.compose.project':self.config['project'],'com.docker.compose.service':'app','com.modular.release_operation':fixture.SOURCE}))
        self.clients=False;self.live_child=False;self.extra_worker=False;self.last_inventory=copy.deepcopy(self.inventory)
        self.reads=[];self.writes=[];self.second_site=None
        def run(argv,**kw):
            self.writes.append((argv,kw))
            if argv[:2]==['docker','inspect']:return json.dumps([self.worker]).encode()
            if argv[:3]==['docker','ps','-q']:return b'child' if self.live_child else b''
            if 'psql' in argv:
                if kw['input'].startswith(b'SELECT count(*)'):return b'1' if self.clients else b'0'
                return json.dumps(self.last_inventory).encode()
            raise AssertionError('Unexpected Docker boundary '+str(argv))
        def read(*a,**kw):
            self.reads.append(kw)
            site=self.second_site if len(self.reads)>1 and self.second_site else self.site
            return dict(image_id=fixture.IMAGE,sites=[copy.deepcopy(site)])
        b.stack.enter_context(patch.object(module,'verify_private_directory',side_effect=lambda path:None))
        b.stack.enter_context(patch.object(module,'_run',side_effect=run))
        b.stack.enter_context(patch.object(module,'DockerObserver',side_effect=lambda config:SimpleNamespace(read=read)))
        b.stack.enter_context(patch.object(module,'snapshots',side_effect=lambda config:[dict(container_id='foreign' if self.extra_worker else config['worker_id'],running=self.extra_worker)]))

    def prove(self):return module.reconcile_retained_sources(self.b.store,self.observer,self.observation,self.inventory)

    def test_actual_resumed_history_live_inventory_and_inert_source_pass_without_mutation(self):
        before=copy.deepcopy((self.config,self.inventory,self.site,self.b.store.source,self.b.store.source_status))
        live,proofs=self.prove()
        self.assertEqual(live,dict(databases=sorted([self.config['sites'][0]['database'],'postgres']),maintenance_relations=[]))
        self.assertEqual(len(proofs),1);self.assertEqual(proofs[0]['database'],self.source)
        self.assertEqual(proofs[0]['checkpoint_operation_id'],fixture.SOURCE)
        self.assertEqual(self.reads,[dict(quiesced=True),dict(quiesced=True)])
        self.assertEqual(before,(self.config,self.inventory,self.site,self.b.store.source,self.b.store.source_status))
        self.assertTrue(all(argv[:2] in (['docker','inspect'],['docker','ps'],['docker','exec']) for argv,kw in self.writes))
        self.assertTrue(all(kw['input'].startswith((b'SELECT ',b'BEGIN READ ONLY;')) for argv,kw in self.writes if 'psql' in argv))

    def test_unknown_database_is_never_connected_to_and_maintenance_refuses(self):
        self.inventory['databases'].append('unknown_private_database')
        with self.assertRaisesRegex(OperatorError,'lacks exact retained'):self.prove()
        self.assertEqual(self.reads,[]);self.assertEqual(self.writes,[])
        self.inventory['databases'].pop();self.inventory['maintenance_relations']=['unexpected']
        with self.assertRaisesRegex(OperatorError,'empty maintenance'):self.prove()
        self.assertEqual(self.reads,[])

    def test_each_actual_source_inertness_gate_is_preserved(self):
        original=copy.deepcopy(self.site)
        mutations=[lambda s:s['native_modules'].append(dict(addon='mp_documents',state='installed')),
            lambda s:s['installations'][0].update(metadata_state='installed'),
            lambda s:s['features'][0].update(feature_state='enabled'),
            lambda s:s['grants'][0].update(state='approved'),
            lambda s:s['bindings'].append(dict(descriptor=dict(consumer_installation_id='installation',provider_installation_id='other',provider_plugin_id='dev.local.documents'))),
            lambda s:s.update(release_digest='sha256:'+'0'*64)]
        for mutate in mutations:
            self.site=copy.deepcopy(original);mutate(self.site)
            with self.subTest(mutation=mutate):
                with self.assertRaises(OperatorError):self.prove()

    def test_clients_live_children_other_workers_and_owned_worker_drift_refuse(self):
        for flag in ('clients','live_child','extra_worker'):
            setattr(self,flag,True)
            with self.subTest(flag=flag):
                with self.assertRaises(OperatorError):self.prove()
            setattr(self,flag,False)
        before=copy.deepcopy(self.worker)
        for change in (dict(Image='sha256:'+'0'*64),dict(State=dict(Running=True,ExitCode=0)),dict(Id='d'*64)):
            self.worker=before|change
            with self.assertRaisesRegex(OperatorError,'exact stopped'):self.prove()

    def test_history_checkpoint_result_and_foreign_store_refuse(self):
        root=self.b.recovery._journal.root
        paths=[root/'result.json',self.b.checkpoint/'database.dump']
        for path in paths:
            raw=path.read_bytes();path.write_bytes(b'{}')
            with self.subTest(path=path):
                with self.assertRaises(OperatorError):self.prove()
            path.write_bytes(raw)
        old=self.b.store.policy['deployments'];self.b.store.policy['deployments']={}
        with self.assertRaisesRegex(OperatorError,'does not authorize'):self.prove()
        self.b.store.policy['deployments']=old

    def test_source_or_inventory_drift_during_observation_refuses(self):
        self.second_site=copy.deepcopy(self.site);self.second_site['release_generation']='unexpected'
        with self.assertRaisesRegex(OperatorError,'changed during observation'):self.prove()
        self.second_site=None;self.reads=[];self.last_inventory['databases'].append('new_database')
        with self.assertRaisesRegex(OperatorError,'inventory changed'):self.prove()

    def test_unknown_pending_source_and_different_image_refuse_before_sql(self):
        current=copy.deepcopy(self.config)
        self.config['image_id']='sha256:'+'0'*64
        with self.assertRaisesRegex(OperatorError,'same-image'):self.prove()
        self.config.update(current)
        root=self.b.recovery._journal.root;path=root/'journal/09-resumed.complete.json';raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(OperatorError,'resumed same-image'):self.prove()
        path.write_bytes(raw)
        self.assertEqual(self.reads,[])

    def test_actual_observer_keeps_default_strict_and_uses_only_supplied_os_store(self):
        observer=object.__new__(DockerObserver);observer.config=self.config;observer._container=lambda service:'db'
        with patch('modular_platform.deployment._run',return_value=json.dumps(self.inventory).encode()):
            with self.assertRaisesRegex(OperatorError,'Unknown sharing database'):observer.removal_site_inventory(self.observation)
            complete=observer.removal_site_inventory(self.observation,store=self.b.store)
        self.assertTrue(complete['complete']);self.assertEqual(len(complete['retained_sources']),1)


if __name__=='__main__':unittest.main()
