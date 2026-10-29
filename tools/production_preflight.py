"""Read-only production-profile preflight for the qualified local R1 adapter.

This is an operator check, never installation approval, initialization or an
automatic account/credential change. It must precede opening production ingress.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from http_profile import production_origin,validate_production_config
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest

SQL="""BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='5s';
SELECT jsonb_build_object(
 'site_id',(SELECT value FROM ir_config_parameter WHERE key='mp.site_id'),
 'release_digest',(SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'),
 'sample_users',(SELECT count(*) FROM res_users WHERE active AND (login='admin' OR login ~ '^(g1_|r0_|r1_|g5_)')),
 'development_modules',(SELECT count(*) FROM ir_module_module WHERE name IN ('mp_feas','mp_r0_fixture','mp_r0_extension') AND state IN ('installed','to install','to upgrade')),
 'base_url',(SELECT value FROM ir_config_parameter WHERE key='web.base.url'),
 'base_url_frozen',(SELECT lower(value) FROM ir_config_parameter WHERE key='web.base.url.freeze'));
ROLLBACK;"""


def check(target,config_path,origin):
    canonical,_=production_origin(origin);settings=validate_production_config(config_path);observer=DockerObserver(target)
    if len(target['sites'])!=1 or settings['database']!=target['sites'][0]['database'] or 'published_release' not in target:
        raise ValueError('One independently selected initialized/published site required')
    runtime=observer.read()
    if runtime['runtime']['inventory_digest']!=target['published_release']['core_inventory_digest']:
        raise ValueError('Actual immutable runtime differs from publication')
    app=observer._container('app');item=json.loads(subprocess.check_output(['docker','inspect',app],timeout=15))[0]
    if (item['Config']['User']!='10001:10001' or not item['HostConfig']['ReadonlyRootfs']
            or item['HostConfig']['PortBindings'] or set(item['NetworkSettings']['Networks'])!={target['project']+'_runtime'}):
        raise ValueError('Application must use its fixed nonroot/read-only/internal-only profile')
    actual=subprocess.check_output(['docker','exec',app,'/venv/bin/python','-c',"from pathlib import Path;print(Path('/run/secrets/odoo_config').read_text(),end='')"],timeout=15).decode()
    if actual.replace('\r\n','\n')!=Path(config_path).read_text(encoding='utf8'):
        raise ValueError('Selected private configuration differs from running application')
    r=subprocess.run(['docker','exec','-i',observer._container('db'),'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',settings['database']],input=SQL.encode(),capture_output=True,check=True,timeout=15);state=json.loads(r.stdout)
    expected=dict(site_id=target['sites'][0]['site_id'],release_digest=data_digest(target['published_release']),sample_users=0,development_modules=0,base_url=canonical,base_url_frozen='true')
    if state!=expected:raise ValueError('Production requires rotated named accounts, disabled initial admin/fixture users, no development modules and a frozen canonical URL')
    return dict(result='passed',site_id=expected['site_id'],image_id=target['image_id'],release_digest=expected['release_digest'],profile=canonical,private_configuration_matches=True,sample_logins_inactive=True,development_modules_absent=True,application_internal_nonroot_readonly=True,read_only=True,limits=['Qualified local single-host Docker adapter only; no production deployment or installation approval.','The OS operator must separately provision/review certificates, credentials, proxy volumes and exact executor authority.'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--deployment-config',type=Path,required=True);p.add_argument('--odoo-config',type=Path,required=True);p.add_argument('--origin',required=True);a=p.parse_args()
    try:result=check(json.loads(a.deployment_config.read_text(encoding='utf8')),a.odoo_config,a.origin)
    except (ValueError,OSError,subprocess.SubprocessError):raise SystemExit('Production preflight refused; reconcile private configuration/account/release defaults before opening ingress')
    print(json.dumps(result))


if __name__=='__main__':main()
