"""Actual source-removal publisher with exact checkpoint dispatch evidence."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.plans import data_digest
import modular_platform.remove_metadata as remove_metadata

SITE=str(UUID('00000000-0000-4000-8000-000000000003'))
WORKSPACE=str(UUID('00000000-0000-4000-8000-000000000004'))
PLUGIN='org.example.notes'
ADDON='mp_example_notes'
OLD='sha256:'+'a'*64
NEW='sha256:'+'b'*64
INVENTORY_DIGEST='sha256:'+'c'*64


def snapshot(release=OLD, profile='r1-native-dispatch-v1', control='paused', uncertain=0, external=0):
    value={'profile':profile,'control':{'state':control},'active_credentials':0,'api_keys':0,
        'uncertain_jobs':uncertain,'release_digest':release,'external_installations':external}
    value['state_digest']=data_digest(value)
    return value


class FakeCursor:
    def __init__(self,case):
        self.case=case;self.query='';self.params=None;self.row=None
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,query,params=None):
        self.query=' '.join(query.split());self.params=params
        if 'to_regclass' in self.query:
            self.row=('mp_job','mp_outbox') if self.case.get('tables') else (None,None)
        elif "ir_config_parameter WHERE key=%s" in self.query:
            key=params[0]
            values={'mp.site_id':SITE,'mp.deployment_id':'deployment','mp.release_generation':str(self.case['data']['generation']-1)}
            self.row=(values[key],)
        elif 'mp_plugin_installation WHERE plugin_id=%s' in self.query:
            self.row=self.case.get('installation',(41,'public-installation','removed',{'runtime':{'addon_name':ADDON}}))
        elif 'mp_workspace_plugin f JOIN mp_workspace w' in self.query:
            self.row=self.case.get('features',[(WORKSPACE,'suspended')])
        elif 'mp_plugin_grant' in self.query:
            self.row=(self.case.get('approved_grants',0),)
        elif 'SELECT count(*) FROM mp_workspace WHERE' in self.query:
            self.row=(self.case.get('workspace_count',1),)
        elif 'ir_module_module WHERE name=ANY' in self.query:
            self.row=(self.case.get('native_modules',0),)
        elif self.query=='SELECT descriptor FROM mp_service_binding':
            self.row=[(self.case['binding'],)] if self.case.get('binding') is not None else []
        elif 'SELECT descriptor FROM mp_service_binding ORDER BY public_id' in self.query:
            self.row=([(self.case['binding'],)] if self.case.get('binding') is not None else [])
        elif 'INSERT INTO ir_config_parameter' in self.query:
            key,value=params[0],params[1]
            self.case['writes'].append((key,value))
            self.case['events'].append(('write',key))
            if self.case.get('fail_write')==key:raise RuntimeError('injected publication SQL failure')
            if key in ('mp.release_generation','mp.release_digest','mp.last_operation_id','mp.active_inventory_digest'):
                if key=='mp.release_digest':self.case['published']['release_digest']=value
                elif key=='mp.release_generation':self.case['published']['generation']=int(value)
                elif key=='mp.last_operation_id':self.case['published']['operation_id']=value
                else:self.case['published']['inventory']=value
                self.case['published']['state_digest']=data_digest({k:v for k,v in self.case['published'].items() if k!='state_digest'})
        else:
            raise AssertionError('unexpected SQL: '+self.query)
    def fetchone(self):return self.row
    def fetchall(self):
        row=self.row
        return row if isinstance(row,list) else ([] if row is None else [row])


class FakeConnection:
    def __init__(self,case):self.case=case
    def __enter__(self):
        self.before=copy.deepcopy(self.case['published']);return self
    def __exit__(self,kind,error,traceback):
        if kind is None:self.case['committed']=True;self.case['events'].append(('commit',None))
        else:
            self.case['rolled_back']=True;self.case['events'].append(('rollback',None))
            self.case['published'].clear();self.case['published'].update(self.before)
        return False
    def cursor(self):return FakeCursor(self.case)
    def close(self):self.case['closed']+=1


class _Options(dict):
    def getint(self,key):return int(self[key])


class FakeConfig:
    def read(self,path):return None
    def __getitem__(self,key):
        return _Options(db_host='db',db_port='5432',db_user='u',db_password='p',db_name='db')


def base_case():
    binding={'consumer_installation_id':'consumer-other','provider_installation_id':'provider-other','provider_plugin_id':'org.example.other'}
    published=snapshot()
    data=dict(site_id=SITE,deployment_id='deployment',operation_id='operation-1',generation=8,
        release_digest=NEW,targets=[dict(installation_id='public-installation',site_id=SITE,workspace_id=WORKSPACE,
        plugin_id=PLUGIN,action='remove')],plugins={},bindings=[binding],permission_changes=[],
        previous_plugins={PLUGIN:{'native_addon':ADDON}},database='db',policy_version=1,
        dispatch_snapshot=snapshot(),dispatch_scope={'site_id':SITE,'release_digest':OLD,'reference':None})
    return {'data':data,'published':published,'writes':[],'events':[],'committed':False,'rolled_back':False,'closed':0,'tables':True,'binding':binding,
            'installation':(41,'public-installation','removed',{'runtime':{'addon_name':ADDON}})}


def run(case,module=remove_metadata):
    real_path=Path
    def fake_pathvalue(value):
        if str(value)=='/opt/modular':return case['inventory']
        if str(value).startswith('/opt/modular/'):return case['inventory']/str(value)[len('/opt/modular/'):]
        return real_path(value)
    stdout=io.StringIO()
    def observe(cursor,scope):
        case['events'].append(('observe',case['published']['release_digest']))
        if scope.site_id!=SITE or scope.release_digest!=case['published']['release_digest']:
            raise ValueError('Fake database site/published release differs from requested observation scope')
        if scope.reference is not None:
            import modular_platform.dispatch_lifecycle as lifecycle
            class EmptyReferenceCursor:
                def execute(self,*args):pass
                def fetchall(self):return []
            verdict=lifecycle.reference_policy(EmptyReferenceCursor(),scope)
            assert verdict['digest']==case['published']['reference_policy_digest']
        if case.get('_observe'):return case['_observe'](cursor,scope)
        return copy.deepcopy(case['published'])
    psycopg2=types.ModuleType('psycopg2');psycopg2.connect=lambda **kwargs:FakeConnection(case)
    with tempfile.TemporaryDirectory(prefix='mp-remove-entry-') as temporary:
        case['inventory']=real_path(temporary)
        (case['inventory']/'distribution-inventory.json').write_text(json.dumps({'artifacts':{},'native_addons':{'base':{}}}))
        with patch.object(module,'Path',side_effect=fake_pathvalue),\
             patch.object(module.configparser,'ConfigParser',FakeConfig),\
             patch.object(sys,'stdin',io.StringIO(json.dumps(case['data']))),\
             patch.dict(sys.modules,{'psycopg2':psycopg2}),\
             patch('modular_platform.dispatch_lifecycle.observe',side_effect=observe),\
             contextlib.redirect_stdout(stdout):
            module.main()
    return json.loads(stdout.getvalue())


class RemoveMetadataEntry(unittest.TestCase):
    def test_durable_exact_checkpoint_success_and_old_check_before_publication(self):
        case=base_case();result=run(case)
        self.assertEqual(result['operation_id'],'operation-1')
        self.assertTrue(result['retained_history_unchanged'])
        self.assertEqual(case['published']['release_digest'],NEW)
        self.assertEqual(case['writes'][-1][0],'mp.active_inventory_digest')
        self.assertEqual(case['closed'],1)
        self.assertEqual(len(case['writes']),4)
        self.assertTrue(case['committed']);self.assertFalse(case['rolled_back'])
        self.assertEqual(case['events'][:2],[('observe',OLD),('observe',OLD)])
        self.assertEqual(case['events'][-1],('commit',None))

    def test_late_final_check_failure_writes_nothing(self):
        case=base_case();calls=[]
        def observe(*args):
            calls.append('observe')
            if len(calls)==2:return snapshot(release=NEW)
            return copy.deepcopy(case['published'])
        case['_observe']=observe
        real_fake=FakeConnection
        with tempfile.TemporaryDirectory(prefix='mp-remove-entry-') as temporary:
            case['inventory']=Path(temporary);(case['inventory']/'distribution-inventory.json').write_text('{"artifacts":{},"native_addons":{}}')
            psycopg2=types.ModuleType('psycopg2');psycopg2.connect=lambda **kwargs:real_fake(case)
            with patch.object(remove_metadata,'Path',side_effect=lambda value:case['inventory'] if str(value)=='/opt/modular' else Path(value)),\
                 patch.object(remove_metadata.configparser,'ConfigParser',FakeConfig),\
                 patch.object(sys,'stdin',io.StringIO(json.dumps(case['data']))),\
                 patch.dict(sys.modules,{'psycopg2':psycopg2}),\
                 patch('modular_platform.dispatch_lifecycle.observe',side_effect=observe):
                with self.assertRaises((AssertionError,ValueError)):remove_metadata.main()
        self.assertEqual(case['writes'],[])
        self.assertTrue(case['rolled_back']);self.assertFalse(case['committed'])

    def test_missing_partial_foreign_stale_open_uncertain_and_no_dispatch_evidence_refuse(self):
        mutations=[
            lambda d:d.pop('dispatch_snapshot'),
            lambda d:d.pop('dispatch_scope'),
            lambda d:d.update(dispatch_scope=None),
            lambda d:d.update(dispatch_snapshot=None),
            lambda d:d.update(dispatch_scope={'site_id':SITE,'release_digest':OLD}),
            lambda d:d.update(dispatch_scope={'site_id':SITE,'release_digest':NEW,'reference':None}),
            lambda d:d.update(dispatch_scope={'site_id':'foreign','release_digest':OLD,'reference':None}),
            lambda d:d.update(dispatch_snapshot=snapshot(release=NEW)),
            lambda d:d.update(dispatch_snapshot=snapshot(control='active')),
            lambda d:d.update(dispatch_snapshot=snapshot(uncertain=1)),
            lambda d:d.update(dispatch_snapshot={},dispatch_scope={'site_id':SITE,'release_digest':OLD,'reference':None}),
        ]
        for mutate in mutations:
            case=base_case();mutate(case['data'])
            with self.subTest(mutation=mutate),self.assertRaises((AssertionError,ValueError)):
                run(case)
            self.assertEqual(case['writes'],[])

    def test_no_dispatch_absent_tables_success_but_populated_tables_refuse(self):
        case=base_case();case['data']['dispatch_snapshot']=None;case['data']['dispatch_scope']=None;case['tables']=False
        result=run(case);self.assertTrue(result['metadata_published'])
        case=base_case();case['data']['dispatch_snapshot']=None;case['data']['dispatch_scope']=None;case['tables']=True
        with self.assertRaises(AssertionError):run(case)
        self.assertEqual(case['writes'],[])

    def test_publication_sql_failure_rolls_back_new_epoch_and_has_no_success(self):
        case=base_case();case['fail_write']='mp.release_digest'
        before=copy.deepcopy(case['published'])
        with self.assertRaisesRegex(RuntimeError,'publication SQL failure'):run(case)
        self.assertTrue(case['rolled_back']);self.assertFalse(case['committed'])
        self.assertEqual(case['published'],before)
        self.assertEqual(case['events'][-1],('rollback',None))

    def test_actual_reference_composed_remove_main_and_generic_default_refusal(self):
        import modular_platform.dispatch_lifecycle as lifecycle
        from reference_operator.executor import ReferenceNativeExecutor
        policy=dict(profile='r1-reference-stateless-v1',site_id=SITE,
            runtime_image='modular-document-stats@sha256:'+'a'*64,
            publication_digest='sha256:'+'b'*64,registrations=[])
        class EmptyReferenceCursor:
            def execute(self,*args):pass
            def fetchall(self):return []
        host=ReferenceNativeExecutor.__new__(ReferenceNativeExecutor)
        host.config={'published_release':{'plugins':[{'runtime':'external_service'}]}}
        source=(ROOT/'packages/platform_sdk/modular_platform/remove_metadata.py').read_text(encoding='utf8')
        with patch.dict(lifecycle.__dict__,dict(lifecycle.__dict__),clear=True):
            module=types.ModuleType('actual_composed_remove_child')
            exec(compile(host._metadata_script('remove_metadata.py',source),module.__name__,'exec'),module.__dict__)
            verdict=lifecycle.reference_policy(EmptyReferenceCursor(),types.SimpleNamespace(reference=policy,site_id=SITE))
            expected=snapshot(profile='r1-reference-stateless-dispatch-v1')
            expected['reference_policy_digest']=verdict['digest']
            expected['state_digest']=data_digest({k:v for k,v in expected.items() if k!='state_digest'})
            case=base_case();case['data']['dispatch_snapshot']=copy.deepcopy(expected)
            case['published']=copy.deepcopy(expected);case['data']['dispatch_scope']['reference']=copy.deepcopy(policy)
            result=run(case,module)
            self.assertTrue(result['metadata_published']);self.assertTrue(case['committed'])
        case=base_case();case['data']['dispatch_snapshot']=copy.deepcopy(expected)
        case['published']=copy.deepcopy(expected);case['data']['dispatch_scope']['reference']=copy.deepcopy(policy)
        with self.assertRaisesRegex(ValueError,'optional reviewed operator source'):run(case)
        self.assertEqual(case['writes'],[]);self.assertTrue(case['rolled_back'])

    def test_retained_live_state_still_refuses_before_publication(self):
        for field,value in [('features',[(WORKSPACE,'enabled')]),('approved_grants',1),('native_modules',1)]:
            case=base_case();case[field]=value
            with self.subTest(field=field),self.assertRaises(AssertionError):run(case)
            self.assertEqual(case['writes'],[])
        case=base_case();case['binding']={'consumer_installation_id':'public-installation','provider_installation_id':'p','provider_plugin_id':'x'}
        case['data']['bindings']=[case['binding']]
        with self.assertRaises(AssertionError):run(case)


if __name__=='__main__':
    unittest.main()
