"""Guarded G4 additions on the existing disposable R1 site; no reseeding."""
import argparse
import json

import r1


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['install','resume-install','provision','update-patches','register-patches']);args=parser.parse_args();state=r1.setup()
    assert '/G4/' in state['evidence'] and state['active_db'].startswith('mp_disposable_r0_r1_')
    if args.action in ['install','resume-install']:
        if args.action=='install' and state.get('g4_install_status'):raise RuntimeError('G4 installation already attempted: inspect/reconcile, never repeat blindly')
        if args.action=='resume-install':
            if state.get('g4_install_status')!='installing':raise RuntimeError('Only known first-attempt failure may resume')
            r1.shell(state,'g4-resume-preflight',"""assert env.cr.dbname.startswith('mp_disposable_r0_r1_')
rows=env['ir.module.module'].search([('name','in',['mp_example_notes','mp_example_notes_labels','mp_example_canvas'])])
assert {r.name:(r.state,r.latest_version) for r in rows}=={'mp_example_notes':('installed','19.0.0.2.0'),'mp_example_notes_labels':('uninstalled',False),'mp_example_canvas':('uninstalled',False)}
env.cr.execute("SELECT revision FROM mp_example_note WHERE public_id='d8243a62-f8ff-46d6-9998-9a2c35f592a0'");assert env.cr.fetchone()==(2,)
env.cr.execute("SELECT to_regclass('mp_example_canvas_board')");assert env.cr.fetchone()==(None,)
print('Known partial install reconciled; base data preserved; new addons only may resume')
""")
        state['g4_install_status']='installing';r1.r0.save(state)
        r1.r0.execute(state,'g4-stop',r1.r0.compose()+['stop','app'])
        update=['-u','mp_example_notes'] if args.action=='install' else []
        r1.r0.execute(state,'g4-'+args.action,r1.r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db']]+update+['-i','mp_example_notes_labels,mp_example_canvas','--stop-after-init','--no-http','--workers=0','--without-demo'])
        state['g4_install_status']='installed_unprovisioned';r1.r0.save(state)
    elif args.action=='provision':
        if state.get('g4_install_status')!='installed_unprovisioned':raise RuntimeError('Requires newly installed, unprovisioned G4 addons')
        log=r1.shell(state,'g4-provision',(r1.r0.ROOT/'tools/g4_seed.py').read_text())
        rows=[line.split('MP_G4_RESULT=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_G4_RESULT=')]
        if len(rows)!=1:raise RuntimeError('Uncertain G4 provisioning: reconcile instead of retrying')
        (r1.r0.LOCAL/'g4-fixtures.json').write_text(json.dumps(json.loads(rows[0]),indent=2)+'\n');state['g4_install_status']='provisioned';r1.r0.save(state)
    elif args.action=='update-patches':
        if state.get('g4_install_status')!='provisioned' or state.get('g4_patch_status'):raise RuntimeError('Patch update requires known provisioned0.1.0 fixture')
        r1.shell(state,'g4-patch-preflight',"""rows=env['ir.module.module'].search([('name','in',['mp_example_notes_labels','mp_example_canvas'])]);assert len(rows)==2
assert all(row.state=='installed' and row.latest_version=='19.0.0.1.0' for row in rows)
env.cr.execute("SELECT revision FROM mp_example_note WHERE public_id='d8243a62-f8ff-46d6-9998-9a2c35f592a0'");assert env.cr.fetchone()==(2,)
print('Known0.1.0 addons verified; explicit0.1.1 source update may proceed')
""")
        state['g4_patch_status']='updating';r1.r0.save(state)
        r1.r0.execute(state,'g4-patch-stop',r1.r0.compose()+['stop','app'])
        r1.r0.execute(state,'g4-patch-update',r1.r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db'],'-u','mp_example_notes_labels,mp_example_canvas','--stop-after-init','--no-http','--workers=0','--without-demo'])
        state['g4_patch_status']='updated_unregistered';r1.r0.save(state)
    elif args.action=='register-patches':
        if state.get('g4_patch_status')!='updated_unregistered':raise RuntimeError('Patch metadata requires completed native update')
        log=r1.shell(state,'g4-patch-metadata',(r1.r0.ROOT/'tools/g4_register_patches.py').read_text())
        rows=[line.split('MP_G4_PATCH=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_G4_PATCH=')]
        if len(rows)!=1:raise RuntimeError('Uncertain patch registration; inspect')
        path=r1.r0.LOCAL/'g4-fixtures.json';fixture=json.loads(path.read_text());fixture['previous_packages']=fixture['packages'];fixture['packages']=json.loads(rows[0]);path.write_text(json.dumps(fixture,indent=2)+'\n')
        state['g4_patch_status']='registered';r1.r0.save(state)


if __name__=='__main__':main()
