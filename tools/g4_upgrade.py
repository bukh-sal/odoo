"""Bounded, checkpointed reference extension upgrade; never a general executor."""
import argparse
import json
import subprocess
from pathlib import Path

import r1


SNAPSHOT="""env.cr.execute('SELECT id,public_id,title,body,author_id,revision,x_notes_labels FROM mp_example_note ORDER BY id')
notes=env.cr.fetchall()
env.cr.execute('SELECT public_id,name,revision,cards,workspace_id FROM mp_example_canvas_board ORDER BY id')
boards=env.cr.fetchall()
print('MP_G4_SNAPSHOT='+json.dumps({'notes':notes,'boards':boards}))
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['backup','apply','verify','register']);args=parser.parse_args();state=r1.setup()
    assert state['g4_install_status']=='provisioned' and state['g4_patch_status']=='registered'
    snapshot=r1.r0.LOCAL/'g4-before-upgrade.json'
    if args.action=='backup':
        if state.get('g4_upgrade_status'):raise RuntimeError('Upgrade checkpoint already attempted; inspect instead of repeating')
        code="import json\nrows=env['ir.module.module'].search([('name','in',['mp_example_notes_labels','mp_example_canvas'])]);assert len(rows)==2\nassert all(row.latest_version=='19.0.0.1.1' and row.state=='installed' for row in rows)\n"+SNAPSHOT
        log=r1.shell(state,'g4-before-upgrade',code)
        rows=[line.split('MP_G4_SNAPSHOT=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_G4_SNAPSHOT=')];assert len(rows)==1
        snapshot.write_text(json.dumps(json.loads(rows[0]),indent=2)+'\n')
        state['g4_upgrade_status']='checkpointing';r1.r0.save(state)
        r1.r0.backup(state)
        image_id=json.loads(subprocess.check_output(['docker','image','inspect',state['image']],text=True))[0]['Id']
        tag='modular-platform:g4-before-labels02'
        r1.r0.execute(state,'g4-pin-old-image',['docker','tag',image_id,tag])
        state['g4_upgrade_status']='backed_up';state['g4_upgrade_backup']=state['backup'];state['g4_previous_image']={'id':image_id,'tag':tag};r1.r0.save(state)
    elif args.action in ['apply','verify']:
        if args.action=='apply':
            if state.get('g4_upgrade_status')!='backed_up':raise RuntimeError('Requires qualified previous checkpoint')
            state['g4_upgrade_status']='migrating';r1.r0.save(state)
            r1.r0.execute(state,'g4-extension-upgrade',r1.r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db'],'-u','mp_example_notes_labels,mp_example_canvas','--stop-after-init','--no-http','--workers=0','--without-demo'])
        elif state.get('g4_upgrade_status')!='migrating':raise RuntimeError('Read-only verification requires recorded migration attempt')
        before=json.loads(snapshot.read_text())
        code="import json\nbefore="+repr(before)+"\n"+SNAPSHOT+"""
assert len(notes)==len(before['notes'])
changed=0
for old,new in zip(before['notes'],notes):
    assert list(new[:5])==old[:5], 'Base identities/content/author changed'
    normalized=list(dict.fromkeys(label.strip().casefold() for label in old[6] or []))
    assert (new[6] or [])==normalized, 'Raw extension values were not migrated'
    effect=normalized!=(old[6] or [])
    assert new[5]==old[5]+int(effect), 'Revision not fenced after migration'
    changed+=effect
assert changed==2, 'Known uppercase fixtures must exercise real native migration'
assert [list(row) for row in boards]==before['boards'], 'Board data changed during extension upgrade'
assert next(row for row in notes if row[1]=='d8243a62-f8ff-46d6-9998-9a2c35f592a0')[5]==2
rows=env['ir.module.module'].search([('name','in',['mp_example_notes_labels','mp_example_canvas'])])
assert {row.name:row.latest_version for row in rows}=={'mp_example_notes_labels':'19.0.0.2.0','mp_example_canvas':'19.0.0.1.2'}
print('MP_G4_UPGRADE=base-and-board-data-preserved-two-extension-values-normalized-with-revision-fences')
"""
        r1.shell(state,'g4-verify-extension-upgrade',code)
        state['g4_upgrade_status']='verified_unregistered';r1.r0.save(state)
    else:
        if state.get('g4_upgrade_status')!='verified_unregistered':raise RuntimeError('Requires verified native upgrade before metadata')
        log=r1.shell(state,'g4-upgrade-package-metadata',(r1.r0.ROOT/'tools/g4_register_patches.py').read_text())
        rows=[line.split('MP_G4_PATCH=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_G4_PATCH=')];assert len(rows)==1
        path=r1.r0.LOCAL/'g4-fixtures.json';fixture=json.loads(path.read_text());fixture.setdefault('package_history',[]).append(fixture['packages']);fixture['packages']=json.loads(rows[0]);path.write_text(json.dumps(fixture,indent=2)+'\n')
        state['g4_upgrade_status']='registered';r1.r0.save(state)


if __name__=='__main__':main()
