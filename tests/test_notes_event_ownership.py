"""Notes owns its event payload/identity; generic transport stays envelope-only."""
from contextlib import contextmanager
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from jsonschema import Draft202012Validator
from modular_platform.contracts import ContractError

TOPIC='org.example.notes.changed'
SITE=UUID('00000000-0000-4000-8000-000000000003')
NOTE=UUID('00000000-0000-4000-8000-000000000002')
CORRELATION=UUID('00000000-0000-4000-8000-000000000005')
EXPECTED=json.loads((ROOT/'examples/mp_example_notes/schemas/notes-changed-v1.json').read_text())


class _EmitScope:
    workspace_id=73
    principal_id=91
    principal_public_id=str(UUID('00000000-0000-4000-8000-000000000009'))
    workspace_public_id=str(UUID('00000000-0000-4000-8000-000000000004'))


class _EnvelopeScope:
    workspace_id=str(UUID('00000000-0000-4000-8000-000000000004'))
    principal_public_id=str(UUID('00000000-0000-4000-8000-000000000009'))


class _Guard:
    def __init__(self):self.calls=[]
    def _mp_guard(self,action):self.calls.append(action);return _EmitScope()


class _EnvelopeGuard:
    def __init__(self):self.calls=[]
    def _mp_guard(self,action):self.calls.append(action);return _EnvelopeScope()


class _Cursor:
    dbname='a01-test'
    def __init__(self):self.executed=[]
    def execute(self,*args):self.executed.append(args)
    def fetchone(self):return (41,)


class _Env:
    def __init__(self):self.cr=_Cursor();self.context={};self.guard=_Guard()
    def __getitem__(self,key):
        if key=='mp.example.note':return self.guard
        raise KeyError(key)


class _Exit(Exception):pass


@contextmanager
def notes_environment():
    saved=dict(sys.modules);saved_path=list(sys.path)
    core=types.ModuleType('odoo');core.addons=types.ModuleType('odoo.addons');core.addons.__path__=[]
    exceptions=types.ModuleType('odoo.exceptions')
    class AccessError(Exception):pass
    exceptions.AccessError=AccessError
    http=types.ModuleType('odoo.http');http.request=None
    def route(*args,**kwargs):
        def decorate(fn):return fn
        return decorate
    http.route=route
    class Controller:pass
    http.Controller=Controller
    identity=types.ModuleType('odoo.addons.mp_identity');release=types.ModuleType('odoo.addons.mp_identity.release')
    release.current_release=lambda env:{'site_id':str(SITE),'release_digest':'sha256:'+'a'*64}
    identity.release=release
    mp_pkg=types.ModuleType('a01_mp_core');mp_pkg.__path__=[]
    controllers=types.ModuleType('a01_mp_core.controllers')
    class PublicError(Exception):pass
    controllers.PublicError=PublicError;controllers.result=lambda value:value;controllers.bounded_body=lambda *args:None
    dispatch=types.ModuleType('a01_mp_core.dispatch')
    class CallFrame:
        def __init__(self,*args):self.args=args
    dispatch.CallFrame=CallFrame;dispatch.authorize_bound=lambda *args:None;dispatch.authorize_origin=lambda *args:None
    jobs=types.ModuleType('a01_mp_core.job_dispatch');jobs._locked_scope=lambda env:_EmitScope()
    psycopg2=types.ModuleType('psycopg2');psycopg2.OperationalError=type('OperationalError',(Exception,),{});psycopg2.IntegrityError=type('IntegrityError',(Exception,),{})
    modules={'psycopg2':psycopg2,'odoo':core,'odoo.addons':core.addons,'odoo.exceptions':exceptions,'odoo.http':http,
        'odoo.addons.mp_identity':identity,'odoo.addons.mp_identity.release':release,
        'a01_mp_core':mp_pkg,'a01_mp_core.controllers':controllers,'a01_mp_core.dispatch':dispatch,
        'a01_mp_core.job_dispatch':jobs}
    sys.modules.update(modules);sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
    try:
        spec=importlib.util.spec_from_file_location('a01_mp_core.events',ROOT/'framework_addons/mp_core/events.py')
        events=importlib.util.module_from_spec(spec);sys.modules[spec.name]=events;spec.loader.exec_module(events)
        mp_pkg.events=events
        mp_odoo=types.ModuleType('odoo.addons.mp_core');mp_odoo.__path__=[];mp_odoo.events=events
        sys.modules['odoo.addons.mp_core']=mp_odoo;sys.modules['odoo.addons.mp_core.events']=events;core.addons.mp_core=mp_odoo
        spec=importlib.util.spec_from_file_location('a01_notes_events',ROOT/'examples/mp_example_notes/events.py')
        app=importlib.util.module_from_spec(spec);sys.modules[spec.name]=app;spec.loader.exec_module(app)
        yield events,app
    finally:
        sys.modules.clear();sys.modules.update(saved)
        sys.path[:]=saved_path


class NotesEventOwnership(unittest.TestCase):
    def test_app_schema_exactly_matches_former_generic_payload_definition(self):
        self.assertEqual(EXPECTED,{
            'type':'object','properties':{
                'note_id':{'type':'string','pattern':r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![\s\S])'},
                'revision':{'type':'integer','minimum':1,'maximum':9007199254740991},
                'change':{'enum':['created','updated','deleted']}},
            'required':['note_id','revision','change'],'additionalProperties':False})

    def test_app_schema_rejects_domain_payload_content_and_shapes(self):
        validator=Draft202012Validator(EXPECTED)
        self.assertTrue(validator.is_valid({'note_id':str(NOTE),'revision':2,'change':'updated'}))
        for payload in (
            {'note_id':str(NOTE),'revision':2,'change':'updated','title':'private'},
            {'note_id':str(NOTE),'revision':2,'change':'updated','labels':[]},
            {'note_id':str(NOTE),'revision':2,'change':'updated','body':'private'},
            {'note_id':str(NOTE),'revision':2,'change':'updated','role':'admin'},
            {'note_id':str(NOTE),'revision':2},
            {'note_id':str(NOTE),'change':'updated'},
            {'note_id':'not-a-uuid','revision':2,'change':'updated'},
            {'note_id':str(NOTE),'revision':True,'change':'updated'},
            {'note_id':str(NOTE),'revision':0,'change':'updated'},
            {'note_id':str(NOTE),'revision':9007199254740992,'change':'updated'},
            {'note_id':str(NOTE),'revision':2,'change':'renamed'},
            {'revision':2,'change':'updated'}):
            with self.subTest(payload=payload):self.assertFalse(validator.is_valid(payload))

    def test_identity_rejects_sequence_and_revision_mismatch(self):
        with notes_environment() as (events,app):
            topic=events.TOPICS[TOPIC]
            self.assertIs(topic.validate_identity,app.identity)
            topic.validate_identity(str(NOTE),2,{'note_id':str(NOTE),'revision':2,'change':'updated'})
            for aggregate,sequence in (('different',2),(str(NOTE),3),(str(NOTE),None)):
                with self.assertRaisesRegex(ContractError,'identity/revision'):
                    topic.validate_identity(aggregate,sequence,{'note_id':str(NOTE),'revision':2,'change':'updated'})

    def test_registered_topic_seam_rejects_payload_identity_and_envelope_domain_errors(self):
        with notes_environment() as (events,app):
            self.assertIn(TOPIC,events.TOPICS)
            topic=events.TOPICS[TOPIC];env=_Env();bound=types.SimpleNamespace(model=_EnvelopeGuard(),binding={'site_id':str(SITE),'workspace_id':_EnvelopeScope.workspace_id})
            base=dict(public_id='event-public',topic=TOPIC,schema_version=1,plugin_id='org.example.notes',
                aggregate_id=str(NOTE),aggregate_sequence=2,site_id=str(SITE),workspace_id=_EnvelopeScope.workspace_id,
                occurred_at='2026-10-29T15:00:00Z',correlation_id=str(CORRELATION),causation_id=None,
                payload={'note_id':str(NOTE),'revision':2,'change':'updated'})
            valid=events._envelope(env,topic,dict(base),bound)
            self.assertEqual(valid['payload'],base['payload'])
            self.assertEqual(bound.model.calls,['read'])
            for change in (
                dict(payload={'note_id':str(NOTE),'revision':2,'change':'updated','title':'private'}),
                dict(payload={'note_id':str(NOTE),'revision':2,'change':'renamed'}),
                dict(aggregate_id=str(CORRELATION)),
                dict(aggregate_sequence=3),
                dict(aggregate_sequence=None),
                dict(payload={'note_id':str(NOTE),'revision':True,'change':'updated'}),
                dict(payload={'note_id':str(NOTE),'change':'updated'}),
                dict(schema_version=2),
                dict(plugin_id='org.example.other')):
                event=copy.deepcopy(base);event.update(change)
                with self.subTest(change=change),self.assertRaises(ContractError):
                    events._envelope(env,topic,event,bound)

    def test_real_emit_refuses_invalid_domain_before_append_and_accepts_positive_control(self):
        with notes_environment() as (events,app):
            env=_Env();appended=[];woke=[];checks=[]
            def append(*args,**kwargs):appended.append((args,kwargs));return 'event-id'
            def locked(env):checks.append('scope');return _EmitScope()
            def release(env):checks.append('release');return {'site_id':str(SITE),'release_digest':'sha256:'+'a'*64}
            with patch.object(events.durable,'append_event',side_effect=append),\
                 patch.object(events,'_locked_scope',side_effect=locked),\
                 patch.object(events,'current_release',side_effect=release),\
                 patch.object(events,'_wake',side_effect=lambda *args:woke.append(args)):
                invalid=[
                    (str(NOTE),2,{'note_id':str(NOTE),'revision':2,'change':'updated',key:'private'})
                    for key in ('title','body','labels','role')]
                invalid.extend([
                    (str(CORRELATION),2,{'note_id':str(NOTE),'revision':2,'change':'updated'}),
                    (str(NOTE),None,{'note_id':str(NOTE),'revision':2,'change':'updated'}),
                    (str(NOTE),2,{'note_id':str(NOTE),'revision':True,'change':'updated'}),
                    (str(NOTE),2,{'note_id':str(NOTE),'revision':9007199254740992,'change':'updated'}),
                    (str(NOTE),2,{'note_id':'not-a-uuid','revision':2,'change':'updated'}),
                    (str(NOTE),2,{'revision':2,'change':'updated'}),
                    (str(NOTE),2,{'note_id':str(NOTE),'change':'updated'}),
                    (str(NOTE),2,{'note_id':str(NOTE),'revision':2})])
                for aggregate,sequence,payload in invalid:
                    with self.subTest(aggregate=aggregate,sequence=sequence,payload=payload),self.assertRaises(ContractError):
                        events.emit(env,TOPIC,aggregate,payload,sequence=sequence,action='create')
                self.assertEqual(appended,[])
                result=events.emit(env,TOPIC,str(NOTE),{'note_id':str(NOTE),'revision':2,'change':'updated'},
                    sequence=2,action='create')
                self.assertEqual(result,'event-id');self.assertEqual(len(appended),1)
                self.assertEqual(env.guard.calls,['create']);self.assertEqual(checks,['scope','release']*(len(invalid)+1))

    def test_actual_topic_delivery_authorization_denial_still_propagates(self):
        with notes_environment() as (events,app):
            from odoo.exceptions import AccessError
            topic=events.TOPICS[TOPIC]
            guard=_EnvelopeGuard()
            bound=types.SimpleNamespace(model=guard,binding={'site_id':str(SITE),'workspace_id':_EnvelopeScope.workspace_id})
            base=dict(public_id='event-public',topic=TOPIC,schema_version=1,plugin_id='org.example.notes',
                aggregate_id=str(NOTE),aggregate_sequence=2,site_id=str(SITE),workspace_id='different-scope',
                occurred_at='2026-10-29T15:00:00Z',correlation_id=str(CORRELATION),causation_id=None,
                payload={'note_id':str(NOTE),'revision':2,'change':'updated'})
            with self.assertRaisesRegex(AccessError,'scope'):
                events._envelope(_Env(),topic,base,bound)
            self.assertEqual(guard.calls,['read'])
            base['workspace_id']=_EnvelopeScope.workspace_id
            with patch.object(guard,'_mp_guard',side_effect=AccessError('current resource denied')):
                with self.assertRaisesRegex(AccessError,'current resource denied'):
                    events._envelope(_Env(),topic,base,bound)

    def test_notes_package_identity_is_the_explicit_successor(self):
        import ast,tomllib
        plugin=tomllib.loads((ROOT/'plugins/notes/plugin.toml').read_text(encoding='utf8'))
        native=ast.literal_eval((ROOT/'examples/mp_example_notes/__manifest__.py').read_text(encoding='utf8'))
        self.assertEqual(plugin['plugin']['version'],'0.2.10')
        self.assertEqual(native['version'],'19.0.0.2.10')

    def test_app_source_has_no_generic_contract_dependency(self):
        source=(ROOT/'examples/mp_example_notes/events.py').read_text(encoding='utf8')
        self.assertNotIn('CONTRACTS',source)
        self.assertNotIn('event-transport.schema.json',source)
        self.assertIn("Path(__file__).parent/'schemas'/'notes-changed-v1.json'",source)


if __name__=='__main__':
    unittest.main()
