"""Guarded R1 development site. No implicit repeat of native initialization."""
import argparse
import configparser
import json
import secrets
import time
import urllib.request
import urllib.error

import r0

r0.LOCAL=r0.ROOT/'.local/r1'
r0.STATE=r0.LOCAL/'state.json'
_compose_env=r0.write_compose_env


def compose_env(state):
    _compose_env(state)
    with (r0.LOCAL/'compose.env').open('a') as handle:handle.write('MP_IMAGE=modular-platform:r1\n')


r0.write_compose_env=compose_env


def setup():
    if not r0.STATE.exists():
        r0.setup();state=r0.load();nonce=secrets.token_hex(6)
        state.update(profile='R1',project='mp-r0-r1'+nonce,active_db='mp_disposable_r0_r1_'+nonce,databases=['mp_disposable_r0_r1_'+nonce],image='modular-platform:r1',evidence='docs/evidence/G3/'+state['run_id'])
        (r0.ROOT/state['evidence']).mkdir(parents=True);r0.save(state)
        config=configparser.ConfigParser();config.read(r0.LOCAL/'odoo.conf')
        config['options']['db_name']=state['active_db'];config['options']['dbfilter']='^'+state['active_db']+'$'
        with (r0.LOCAL/'odoo.conf').open('w') as handle:config.write(handle)
        compose_env(state)
    state=r0.load()
    if state.get('profile')!='R1':raise RuntimeError('Unexpected site state')
    print(json.dumps({k:state[k] for k in ['profile','project','active_db','port']}));return state


def shell(state,label,code):
    return r0.execute(state,label,r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0'],input_bytes=code.encode())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','build','init','seed','install-shell','up','down']);args=parser.parse_args();state=setup()
    if args.action=='build':
        r0.execute(state,'r1-build',['docker','build','-f','deploy/Dockerfile','--build-arg','DISTRIBUTION_POLICY=deploy/distribution-r1.json','--build-arg','RUNTIME_REQUIREMENTS=deploy/requirements-r1.lock','--build-arg','SDK_PYTHONPATH=/opt/modular/packages/platform_sdk','-t','modular-platform:r1','.'])
    elif args.action=='init':
        if state.get('install_status'):raise RuntimeError('Installation already attempted; inspect before retry')
        r0.seed_volumes(state);r0.execute(state,'r1-db',r0.compose()+['up','-d','--wait','db']);r0.inside(state,'bootstrap')
        state['install_status']='installing';r0.save(state)
        r0.execute(state,'r1-install',r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db'],'-i','mp_example_notes','--stop-after-init','--no-http','--workers=0','--without-demo'])
        state['install_status']='installed_unseeded';r0.save(state)
    elif args.action=='seed':
        if state.get('install_status')!='installed_unseeded':raise RuntimeError('Requires installed, unseeded site')
        log=shell(state,'r1-provision',(r0.ROOT/'tools/r1_seed.py').read_text())
        rows=[line.split('MP_R1_RESULT=',1)[1] for line in log.read_text(errors='replace').splitlines() if line.startswith('MP_R1_RESULT=')]
        if len(rows)!=1:raise RuntimeError('Uncertain provisioning; reconcile instead of retry')
        (r0.LOCAL/'fixtures.json').write_text(json.dumps(json.loads(rows[0]),indent=2)+'\n');state['install_status']='seeded';r0.save(state)
    elif args.action=='up':
        if state.get('install_status')!='seeded':raise RuntimeError('Site is not provisioned')
        r0.execute(state,'r1-up',r0.compose()+['up','-d','app','edge'])
        deadline=time.monotonic()+30
        http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while True:
            try:
                with http.open(f"http://127.0.0.1:{state['port']}/web/login",timeout=2) as response:
                    body=response.read()
                    if response.code==200 and b'name="login"' in body and b'name="password"' in body:break
            except (OSError,urllib.error.URLError):pass
            if time.monotonic()>=deadline:raise RuntimeError('Development login readiness timed out; inspect app logs')
            time.sleep(0.25)
        print(json.dumps({'development_login_readiness':'passed','release_readiness':'not_qualified_G7'}))
    elif args.action=='install-shell':
        if state.get('install_status')!='seeded' or state.get('shell_install_status'):raise RuntimeError('Shell install requires seeded site and no previous attempt')
        r0.execute(state,'r1-shell-stop',r0.compose()+['stop','app'])
        state['shell_install_status']='installing';r0.save(state)
        r0.execute(state,'r1-shell-install',r0.compose()+['run','--rm','--no-deps','--entrypoint','python','maintenance','odoo-bin','-c','/run/secrets/odoo_config','-d',state['active_db'],'-i','mp_shell','--stop-after-init','--no-http','--workers=0','--without-demo'])
        state['shell_install_status']='installed';r0.save(state)
    elif args.action=='down':r0.execute(state,'r1-stop',r0.compose()+['stop'])


if __name__=='__main__':main()
