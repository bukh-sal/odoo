"""Once-only real approved lifecycle on the populated event fixture.

One new synthetic workspace receives the already pinned Notes package. Existing
A/B scopes, artifacts and records are retained. No new image or DB is created.
"""
import argparse,json,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
f=j.f;f.OUTPUT=OUT;state=f.load(j.LOCAL/'state.json');f.guard(state)
parser=argparse.ArgumentParser();parser.add_argument('--resume-plan',action='store_true');args=parser.parse_args()
assert state['phase']==('lifecycle-workspace-C-01' if args.resume_plan else 'carryforward_host_controls_verified')
assert f.load(OUT/'legacy-host-revalidation.json')['result']=='passed_legacy_host_revalidation'
marker=j.LOCAL/'carryforward-scoped-install-01.json';fixture=f.load(j.LOCAL/'fixtures.json')
if args.resume_plan:
    old=f.load(marker);assert old['state']=='provisioning_owned_workspace';ident=old['workspace_id'];operation=old['operation_id'];assert fixture['workspaces']['C']['public_id']==ident
    database=j.LOCAL/'operator/control/control.sqlite3';assert database.is_file()
    with sqlite3.connect(database) as db:assert db.execute('SELECT count(*) FROM operations WHERE operation_id=?',[operation]).fetchone()[0]==0
    child=json.loads(__import__('subprocess').check_output(['docker','inspect',state['project']+'-lifecycle-workspace-C-01']))[0];assert not child['State']['Running'] and child['State']['ExitCode']==0
    f.save('scoped-install-planning-correction.json',dict(result='fixture_driver_corrected_before_plan_or_operation',workspace_provisioned_once=True,operation_registered=False,diagnosis='Driver supplied only the state to prepare_current_install_targets; restore complete observer document with environment/provenance/Python. Resume planning only, not workspace creation or any native lifecycle command.'))
else:
    assert not marker.exists() and 'C' not in fixture['workspaces']
    ident=str(uuid4());operation=str(uuid4());f.write(marker,dict(state='provisioning_owned_workspace',workspace_id=ident,operation_id=operation))
    code="import json\nenv.cr.rollback()\nassert env.cr.dbname=="+repr(state['active_db'])+"\nenv.cr.execute('SELECT state,generation FROM mp_dispatch_control');assert env.cr.fetchone()==('paused',18)\nenv.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',["+repr(fixture['users']['alice']['principal_id'])+"]);principal=env.cr.fetchone()[0]\nw=env['mp.workspace'].create(dict(name='Owned lifecycle C',public_id="+repr(ident)+"))\nenv['mp.membership'].create(dict(principal_id=principal,workspace_id=w.id,role='administrator',state='active'))\nenv.cr.commit();print('MP_WORKSPACE_C='+json.dumps(dict(id=w.id,public_id=w.public_id,name=w.name)))"
    raw=f.native(state,'lifecycle-workspace-C-01',[],code)
    rows=[json.loads(line.split('MP_WORKSPACE_C=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_WORKSPACE_C=')];assert len(rows)==1
    fixture['workspaces']['C']=rows[0];f.write(j.LOCAL/'fixtures.json',fixture)
target=j.LOCAL/'operator/target.json';config=f.load(target);assert config['generation']==2 and config['image_id']==state['image_id']
reader=DockerObserver(config);catalog=Catalog(j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'),readonly=True);snapshot=catalog.snapshot()
observation=reader.read();document=reader.state(observation,snapshot);before=document['state']
if args.resume_plan:assert f.load(OUT/'scoped-install-before.json')==before
else:f.save('scoped-install-before.json',before)
targets=[dict(installation_id=installation_id(observation['sites'][0],'org.example.notes'),site_id=state['site_id'],workspace_id=ident,plugin_id='org.example.notes',action='install')]
bundle=prepare_current_install_targets(document,observation['sites'],snapshot,activation_targets=targets,operation_id=operation,created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
f.save('scoped-install-bundle.json',bundle)
f.write(marker,dict(state='prepared',operation_id=operation,plan_hash=bundle['plan_hash'],workspace_id=ident))
prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
ops=prefix+['operations','--store',str(j.LOCAL/'operator/control')];options=['--deployment-config',str(target),'--catalog',str(j.LOCAL/'operator/catalog')]
f.command('lifecycle-C-register-01',ops+['register','--bundle',str(OUT/'scoped-install-bundle.json')]+options)
f.command('lifecycle-C-approve-01',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions']+options)
f.write(marker,dict(state='applying',operation_id=operation,plan_hash=bundle['plan_hash'],workspace_id=ident));f.phase(state,'carryforward_scoped_install_applying')
completed=json.loads(f.command('lifecycle-C-apply-01',prefix+['plugin','apply',operation,'--store',str(j.LOCAL/'operator/control')]+options,timeout=600))
assert completed['state']=='completed'
current=f.load(target);assert current['generation']==3 and current['image_id']==state['image_id']
reader=DockerObserver(current);after=reader.state(reader.read(),snapshot)['state']
assert len(after['installations'])==7 and all(i in after['installations'] for i in before['installations'])
f.save('scoped-install-after.json',after);fixture['bindings']['C']=next(b for b in after['bindings'] if b['workspace_id']==ident and b['consumer_installation_id']==targets[0]['installation_id'] and b['alias']=='documents');f.write(j.LOCAL/'fixtures.json',fixture)
f.save('scoped-install-result.json',dict(result='completed',operation_id=operation,plan_hash=bundle['plan_hash'],workspace_id=ident,configuration=current,completed=completed,image_unchanged=True,original_A_B_installations_retained=True,limits=['Real approved scoped install/fence/checkpoint/reconciliation/enable, not a new-image upgrade or fault/restore qualification.','Known old-image browser timer/history/Note batch fixes still await the planned immutable core/plugin upgrades.']))
f.write(marker,dict(state='completed',operation_id=operation,workspace_id=ident));f.phase(state,'carryforward_scoped_install_completed');f.guard(state);print('Real approved scoped install completed on the same populated image/site, generation3.')
