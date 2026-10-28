"""Declared native provider entrypoint; imported only after trusted addon load."""
import json
from odoo.addons.mp_core.registry import Method, register
from modular_platform.contracts import CONTRACTS
_note_schema=json.loads((CONTRACTS/'documents.schema.json').read_text())['$defs']['note']
_uuid_schema=_note_schema['properties']['id']
_list_schema={'type':'object','properties':{'items':{'type':'array','maxItems':100,'items':_note_schema},'next_cursor':{'type':['string','null']}},'required':['items','next_cursor'],'additionalProperties':False}
_delete_schema={'type':'object','properties':{'id':_uuid_schema,'deleted':{'const':True}},'required':['id','deleted'],'additionalProperties':False}
class NotesService:
    methods = {
    name:Method('mp.example.note','_mp_service_'+name,name+'_input','documents.schema.json','org.example.notes:notes.'+permission,mutation,action,_list_schema if name=='list' else _delete_schema if name=='delete' else _note_schema)
    for name,permission,mutation,action in [('list','read',False,'read'),('get','read',False,'read'),('create','write',True,'create'),('update','write',True,'write'),('delete','delete',True,'unlink')]
    }

register('org.example.notes.documents','1.0','org.example.notes',NotesService.methods)
