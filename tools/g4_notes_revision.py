"""One guarded final Notes patch for native deletion revision enforcement."""
import json
import r1


def main():
    state=r1.setup()
    if state.get('g4_notes_revision_status'):raise RuntimeError('Notes revision patch already attempted; reconcile, never repeat blindly')
    assert state['g4_upgrade_status']=='registered'
    r1.shell(state,'g4-notes-cas-preflight',"""row=env['ir.module.module'].search([('name','=','mp_example_notes')]);assert row.state=='installed' and row.latest_version=='19.0.0.2.0'
env.cr.execute("SELECT public_id,title,body,revision FROM mp_example_note WHERE public_id='d8243a62-f8ff-46d6-9998-9a2c35f592a0'");row=env.cr.fetchone();assert row and row[3]==2
print('Known Notes0.2.0/journal2 verified; non-schema0.2.1 patch may proceed')
""")
    state['g4_notes_revision_status']='checkpointing';r1.r0.save(state);r1.r0.backup(state)
    state['g4_notes_revision_status']='updating';r1.r0.save(state)
    r1.r0.execute(state,'g4-notes-cas-build',['docker','build','-f','deploy/Dockerfile','--build-arg','DISTRIBUTION_POLICY=deploy/distribution-r1.json','--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',state['image'],'.'])
    r1.r0.execute(state,'g4-notes-cas-update',r1.r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db'],'-u','mp_example_notes','--stop-after-init','--no-http','--workers=0','--without-demo'])
    log=r1.shell(state,'g4-notes-cas-metadata',(r1.r0.ROOT/'tools/g4_register_patches.py').read_text())
    rows=[line.split('MP_G4_PATCH=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_G4_PATCH=')];assert len(rows)==1
    path=r1.r0.LOCAL/'g4-fixtures.json';fixture=json.loads(path.read_text());fixture.setdefault('package_history',[]).append(fixture['packages']);fixture['packages']=json.loads(rows[0]);path.write_text(json.dumps(fixture,indent=2)+'\n')
    state['g4_notes_revision_status']='registered';r1.r0.save(state)


if __name__=='__main__':main()
