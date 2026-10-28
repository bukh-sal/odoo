"""Separate disposable G5 core/control site; never reinitialize G4 targets."""
import argparse
import configparser
import json
from pathlib import Path
import secrets
import subprocess
from uuid import uuid4

import r0
import sys
sys.path.insert(0,str(r0.ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import OperatorStore

r0.LOCAL=r0.ROOT/'.local/g5'
r0.STATE=r0.LOCAL/'state.json'
_compose=r0.compose
r0.compose=lambda:_compose()+['-f',str(r0.ROOT/'deploy/compose-g5.yaml')]


def setup():
    if r0.STATE.exists():
        state=r0.load()
        if state.get('profile')!='G5':raise RuntimeError('Unexpected existing site; inspect without resetting')
        return state
    r0.setup();state=r0.load();nonce=secrets.token_hex(6)
    state.update(profile='G5',project='mp-r0-r1g5'+nonce,active_db='mp_disposable_r0_r1_g5_'+nonce,
        databases=['mp_disposable_r0_r1_g5_'+nonce],image='modular-platform:g5-'+nonce,
        evidence='docs/evidence/G5/'+r0.now()+'-site',deployment_id=str(uuid4()),site_id=str(uuid4()),stage='empty')
    (r0.ROOT/state['evidence']).mkdir(parents=True);r0.save(state)
    config=configparser.ConfigParser();config.read(r0.LOCAL/'odoo.conf')
    config['options']['db_name']=state['active_db'];config['options']['dbfilter']='^'+state['active_db']+'$'
    config['options']['addons_path']='/opt/modular/addons'
    with (r0.LOCAL/'odoo.conf').open('w') as stream:config.write(stream)
    r0.write_compose_env(state)
    with (r0.LOCAL/'compose.env').open('a') as stream:stream.write('MP_IMAGE='+state['image']+'\n')
    return state


def shell(state,label,code):
    return r0.execute(state,label,r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance',
        'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0'],input_bytes=code.encode())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','build','init','seed','up','inspect']);args=parser.parse_args();state=setup()
    if state.get('worker_id') and args.action in ('build','init','seed','up'):
        raise RuntimeError('G5 is managed by the independent executor; use a new recorded candidate and exact approved operation, not the original bootstrap/Compose mutation path')
    if args.action=='build':
        if state.get('build_status')=='building':raise RuntimeError('Build may still be running; inspect before restarting')
        state['build_status']='building';r0.save(state)
        r0.execute(state,'g5-core-build',['docker','build','-f','deploy/Dockerfile','--build-arg','DISTRIBUTION_POLICY=deploy/distribution-r1.json',
            '--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t',state['image'],'.'])
        state['image_id']=subprocess.check_output(['docker','image','inspect',state['image'],'--format','{{.Id}}']).decode().strip()
        state['build_status']='built';r0.save(state)
    elif args.action=='init':
        if state.get('install_status'):raise RuntimeError('Native initialization already attempted; inspect/reconcile instead of repeating')
        if state.get('build_status')!='built':raise RuntimeError('Requires pinned built G5 image')
        store=OperatorStore(r0.ROOT/'.local/operator/control')
        policy=store.authorize_deployment(state['deployment_id'],[state['site_id']])
        targets=r0.ROOT/'.local/operator/targets'
        for path in targets.glob('*.json'):
            value=json.loads(path.read_text());value['operator_authorization_generation']=policy['authorization_generation'];value['policy_version']=policy['policy_version']
            path.write_text(json.dumps(value,indent=2)+'\n')
        target={'schema_version':1,'deployment_id':state['deployment_id'],'project':state['project'],
            'sites':[{'site_id':state['site_id'],'database':state['active_db']}],'image_id':state['image_id'],
            'generation':1,'policy_version':policy['policy_version'],'operator_authorization_generation':policy['authorization_generation'],
            'release_created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        target_path=targets/'g5.json'
        if target_path.exists():raise RuntimeError('G5 target already enrolled; reconcile without repeating init')
        with target_path.open('x') as stream:stream.write(json.dumps(target,indent=2)+'\n')
        r0.seed_volumes(state);r0.execute(state,'g5-db',r0.compose()+['up','-d','--wait','db']);r0.inside(state,'bootstrap')
        state['install_status']='installing_core';r0.save(state)
        r0.execute(state,'g5-core-init',r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin',
            '-c','/run/secrets/odoo_config','-d',state['active_db'],'-i','mp_shell','--stop-after-init','--no-http','--workers=0','--without-demo'])
        state['install_status']='core_installed_unseeded';r0.save(state)
    elif args.action=='seed':
        if state.get('install_status')!='core_installed_unseeded':raise RuntimeError('Requires new unseeded core site')
        code=(r0.ROOT/'tools/g5_seed.py').read_text().replace('G5_SITE_UUID',state['site_id']).replace('G5_DEPLOYMENT_UUID',state['deployment_id'])
        log=shell(state,'g5-core-provision',code)
        rows=[line.split('MP_G5_RESULT=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_G5_RESULT=')]
        if len(rows)!=1:raise RuntimeError('Uncertain provisioning; reconcile without repeating')
        (r0.LOCAL/'fixtures.json').write_text(json.dumps(json.loads(rows[0]),indent=2)+'\n')
        state['install_status']='seeded_core';state['stage']='core_ready';r0.save(state)
    elif args.action=='up':
        if state.get('install_status')!='seeded_core':raise RuntimeError('Requires explicitly provisioned core')
        r0.execute(state,'g5-up',r0.compose()+['up','-d','app','edge'])
    elif args.action=='inspect':
        r0.execute(state,'g5-status',r0.compose()+['ps','--format','json'])
    print(json.dumps({key:state.get(key) for key in ['profile','project','active_db','port','image','build_status','install_status']}))


if __name__=='__main__':main()
