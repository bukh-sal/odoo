"""Fresh old46 Aurora source from the retained sealed consumer, no resets."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.local/addon-cleanup/aurora46'
KIT=ROOT/'.local/releases/foundation-r1-core46'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','initialize','seed','workflow'])
    p.add_argument('--label',default='source');a=p.parse_args()
    assert a.label.replace('-','').isalnum()
    setup=json.loads((ROOT/'.local/foundation-release/clean-core46/operator-setup.json').read_bytes())
    assert Path(sys.executable).resolve()==Path(setup['python']).resolve()
    source=Path(setup['source']);sys.path[:0]=[str(source/'release'),str(source/'tools'),str(source/'packages/platform_sdk')]
    from initialize_reference import Reference,configuration,write
    from modular_platform.catalog import Catalog
    from modular_platform.operator_os import protect_directory
    if a.phase=='prepare':
        assert not WORK.exists(),'Never reset or replay an existing source'
        protect_directory(WORK);private=protect_directory(WORK/'private')
        write(WORK/'operator-setup.json',dict(setup,private=str(private)))
        catalog=Catalog(private/'catalog',configuration(KIT/'plugins/curated-trust.json'))
        for row in json.loads((KIT/'plugins/index.json').read_bytes())['packages']:
            catalog.add(KIT/row['file'],expected_digest=row['digest'])
    options=SimpleNamespace(kit=KIT,workdir=WORK,reference_fixture=True,port=18163,
        subnets=['10.203.158.0/28','10.203.158.16/28'],native_app='mp_aurora_tasks')
    if a.phase=='prepare':site=Reference(options)
    else:
        site=Reference.__new__(Reference);site.kit,site.work,site.args=KIT,WORK,options
        site.operator=json.loads((WORK/'operator-setup.json').read_bytes())
        site.private,site.local=WORK/'private',WORK/'private/reference'
    if a.phase in ('prepare','initialize'):
        getattr(site,a.phase)();return
    code='''
import json
from odoo.fields import Command
assert env.cr.dbname == EXPECTED_DB
alice=env['res.users'].search([('login','=','r1_alice')],limit=1)
bob=env['res.users'].search([('login','=','r1_bob')],limit=1)
operator=env['res.users'].search([('login','=','r1_operator')],limit=1)
assert alice and bob and operator
'''
    target=json.loads((site.local/'operator/target.json').read_bytes())
    state=site.state();state.update(database=target['sites'][0]['database'],image_id=target['image_id'])
    if a.phase=='seed':
        assert not (site.local/'app-fixtures.json').exists()
        code+='''
assert not env['mp.aurora.task.list'].search_count([('name','=','AR source schedule')])
board=env['mp.aurora.task.list'].with_user(alice).create(dict(name='AR source schedule',member_ids=[Command.link(bob.id)]))
stages=env['mp.aurora.task.stage'].with_user(alice).create([dict(name='Queued',list_id=board.id),dict(name='Done',done=True,list_id=board.id)])
task=env['mp.aurora.task'].with_user(bob).create(dict(name='AR retained Aurora task',list_id=board.id,stage_id=stages[0].id,assignee_id=bob.id))
env.cr.commit()
print('AR_AURORA='+json.dumps(dict(board=board.id,task=task.id,queued=stages[0].id,done=stages[1].id)))
'''
    else:
        assert not (site.local/('workflow-'+a.label+'.json')).exists()
        fixture=json.loads((site.local/'app-fixtures.json').read_bytes());code+='FIXTURE='+repr(fixture)+'\n'+'''
from odoo.exceptions import AccessError
task=env['mp.aurora.task'].with_user(bob).browse(FIXTURE['task'])
assert task.name=='AR retained Aurora task'
assert task.write(dict(stage_id=FIXTURE['done']))
assert task.stage_id.id==FIXTURE['done']
views=task.get_views([(False,'list'),(False,'form')]);assert {'list','form'} <= views['views'].keys()
try:task.with_user(operator).read(['name'])
except AccessError:pass
else:raise AssertionError('Unrelated actor could read Aurora task')
env.cr.commit()
print('AR_AURORA='+json.dumps(dict(result='passed',native_views=True,workflow=True,unrelated_actor_denied=True)))
'''
    raw=site.native(state,'ar-aurora-'+a.label+'-'+a.phase,[],f"EXPECTED_DB={state['database']!r}\n"+code)
    result,=[json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('AR_AURORA=')]
    write(site.local/('app-fixtures.json' if a.phase=='seed' else 'workflow-'+a.label+'.json'),result)
    print(json.dumps(result))


if __name__=='__main__':main()
