"""One-time operator fixture. Package bytes/inventory supply plugin metadata."""
import hashlib
import json
from pathlib import Path
import tomllib
from uuid import uuid4
import zipfile

from modular_platform.contracts import normalize_manifest,resolve_ui
from odoo.addons.mp_identity.scopes import scoped_environment

assert env.cr.dbname.startswith('mp_disposable_r0_r1_')
assert not env['mp.plugin.installation'].search_count([('plugin_id','=','org.example.canvas')])
inventory=json.loads(Path('/opt/modular/distribution-inventory.json').read_text());packages={}
for plugin,descriptor in inventory['artifacts'].items():
    artifact=Path('/opt/modular/artifacts')/descriptor['file'];assert 'sha256:'+hashlib.sha256(artifact.read_bytes()).hexdigest()==descriptor['digest']
    with zipfile.ZipFile(artifact) as archive:manifest=normalize_manifest(tomllib.loads(archive.read(plugin+'/plugin.toml').decode()))
    assert manifest['plugin']['id']==plugin and manifest['plugin']['version']==descriptor['version'];packages[plugin]=(manifest,descriptor)
resolve_ui([manifest for manifest,descriptor in packages.values()])
installations={}
for plugin,(manifest,descriptor) in packages.items():
    row=env['mp.plugin.installation'].search([('plugin_id','=',plugin)])
    values={'version':descriptor['version'],'artifact_digest':descriptor['digest'],'manifest':manifest}
    if row:row.write(values)
    else:row=env['mp.plugin.installation'].create({**values,'plugin_id':plugin,'runtime':'native'})
    installations[plugin]=row
site=env['ir.config_parameter'].get_param('mp.site_id');bindings={};boards={};spaces={}
for name,login in [('Personal','r1_alice'),('Research','r1_bob')]:
    workspace=env['mp.workspace'].search([('name','=',name)]);assert len(workspace)==1;spaces[name]=workspace.public_id
    bindings[name]={}
    for plugin,installation in installations.items():
        feature=env['mp.workspace.plugin'].search([('workspace_id','=',workspace.id),('plugin_id','=',plugin)])
        if not feature:env['mp.workspace.plugin'].create({'workspace_id':workspace.id,'plugin_id':plugin,'installation_id':installation.id})
        bindings[name][plugin]={}
        for requirement in installation.manifest['services']['requires']:
            provider_plugin='org.example.notes' if requirement['id']=='org.example.notes.documents' else plugin
            provider=installations[provider_plugin];version=str(requirement['contract_major'])+'.0'
            row=env['mp.service.binding'].search([('consumer_id','=',installation.id),('workspace_id','=',workspace.id),('alias','=',requirement['alias'])])
            if not row:
                descriptor={'schema_version':1,'binding_id':str(uuid4()),'site_id':site,'workspace_id':workspace.public_id,'consumer_installation_id':installation.public_id,'alias':requirement['alias'],'service_id':requirement['id'],'contract_major':requirement['contract_major'],'api_version':version,'provider_plugin_id':provider_plugin,'provider_installation_id':provider.public_id,'generation':1,'optional':False}
                row=env['mp.service.binding'].create({'public_id':descriptor['binding_id'],'workspace_id':workspace.id,'consumer_id':installation.id,'alias':requirement['alias'],'descriptor':descriptor})
            bindings[name][plugin][requirement['alias']]=row.descriptor
        for grant in installation.manifest['permissions']['requests']:
            env['mp.plugin.grant'].create({'workspace_id':workspace.id,'installation_id':installation.id,'capability':grant['capability']})
    actor=env['res.users'].search([('login','=',login)]);assert len(actor)==1
    scoped=scoped_environment(env(user=actor.id,su=False,context={}),workspace.public_id)
    note=scoped['mp.example.note'].search([],limit=1)
    board=scoped['mp.example.canvas.board'].create({'name':name+' ideas','cards':[{'id':str(uuid4()),'text':'Explore a useful idea','lane':'inbox','note_id':note.public_id}]})
    boards[name]=board._dto()
alice=env['res.users'].search([('login','=','r1_alice')]);scoped=scoped_environment(env(user=alice.id,su=False,context={}),spaces['Personal'])
migration=scoped['mp.example.note'].create({'title':'Labels migration fixture','body':'Base content must survive the extension upgrade.','x_notes_labels':['Important','Next']})
result={'database':env.cr.dbname,'workspaces':spaces,'boards':boards,'bindings':bindings,'installations':{p:i.public_id for p,i in installations.items()},'packages':{p:d for p,(m,d) in packages.items()},'migration_note':migration._dto()}
env.cr.commit();env.registry.signal_changes()
print('MP_G4_RESULT='+json.dumps(result))
