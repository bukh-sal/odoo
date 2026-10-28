"""Explicit operator provisioning of a NEW disposable R1 development site."""
from uuid import uuid4
from pathlib import Path
import json
import hashlib

from odoo.addons.mp_identity.scopes import scoped_environment

assert env.cr.dbname.startswith('mp_disposable_r0_r1_')
assert not env['mp.principal'].search_count([]),'Provisioned site cannot be seeded twice'
site=str(uuid4());env['ir.config_parameter'].set_param('mp.site_id',site)
password=Path('/run/mp-bootstrap/password').read_text().strip()
users={};principals={}
for key,kind in [('alice','human'),('bob','human'),('outsider','human'),('worker','service')]:
    user=env['res.users'].with_context(no_reset_password=True).create({'name':key.title(),'login':'r1_'+key,'password':password,'group_ids':[(6,0,env.ref('base.group_user').ids)]})
    users[key]=user;principals[key]=env['mp.principal'].create({'name':user.name,'user_id':user.id,'kind':kind})
workspaces={key:env['mp.workspace'].create({'name':'Personal' if key=='A' else 'Research'}) for key in ['A','B']}
members={}
for who,where,role in [('alice','A','editor'),('alice','B','viewer'),('bob','B','editor'),('worker','A','viewer')]:
    members[who+where]=env['mp.membership'].create({'principal_id':principals[who].id,'workspace_id':workspaces[where].id,'role':role})
manifest=json.loads(Path('/opt/modular/packages/contracts/examples/v1/manifest-native.json').read_text())
inventory=json.loads(Path('/opt/modular/distribution-inventory.json').read_text())
source_digest=hashlib.sha256(json.dumps({p:h for p,h in inventory['files'].items() if p.startswith('addons/mp_example_notes/')},sort_keys=True).encode()).hexdigest()
installation=env['mp.plugin.installation'].create({'plugin_id':'org.example.notes','version':'0.1.0','artifact_digest':'development-source:sha256:'+source_digest,'runtime':'native','manifest':manifest})
bindings={}
for key,workspace in workspaces.items():
    env['mp.workspace.plugin'].create({'workspace_id':workspace.id,'plugin_id':installation.plugin_id,'installation_id':installation.id})
    ident=str(uuid4());descriptor={'schema_version':1,'binding_id':ident,'site_id':site,'workspace_id':workspace.public_id,'consumer_installation_id':installation.public_id,'alias':'documents','service_id':'org.example.notes.documents','contract_major':1,'api_version':'1.0','provider_plugin_id':'org.example.notes','provider_installation_id':installation.public_id,'generation':1,'optional':False}
    env['mp.service.binding'].create({'public_id':ident,'workspace_id':workspace.id,'consumer_id':installation.id,'alias':'documents','descriptor':descriptor});bindings[key]=descriptor
objects={}
for key,who in [('A','alice'),('B','bob')]:
    scoped=scoped_environment(env(user=users[who].id,su=False,context={}),workspaces[key].public_id)
    objects[key]=scoped['mp.example.note'].create({'title':'Welcome to Notes' if key=='A' else 'Research journal','body':'A private place for ideas, decisions and next steps.' if key=='A' else 'This workspace is read-only for Alice.'})
env.cr.commit()
print('MP_R1_RESULT='+json.dumps({'database':env.cr.dbname,'site_id':site,'users':{k:{'id':u.id,'login':u.login,'principal_id':principals[k].public_id} for k,u in users.items()},'workspaces':{k:{'id':w.id,'public_id':w.public_id} for k,w in workspaces.items()},'memberships':{k:m.id for k,m in members.items()},'objects':{k:{'id':v.id,'public_id':v.public_id} for k,v in objects.items()},'installation_id':installation.public_id,'bindings':bindings},sort_keys=True))
