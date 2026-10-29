"""Positive/negative operator preflight, Compose resolution and retired logins."""
import configparser
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity'


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');target=load(LOCAL/'operator/target.json');dest=OUTPUT/'production-preflight.json';assert not dest.exists();results=[]
    base=[sys.executable,'-X','utf8','tools/production_preflight.py','--deployment-config',str(LOCAL/'operator/target.json'),'--odoo-config',str(LOCAL/'odoo.conf'),'--origin',state['origin']]
    positive=subprocess.run(base,capture_output=True,timeout=60);assert positive.returncode==0;report=json.loads(positive.stdout);assert report['read_only'] and report['sample_logins_inactive']
    for label,changes in [('untrusted_proxy',dict(proxy_mode='False')),('development_flag',dict(dev_mode='all')),('different_private_config',dict(db_password='INTENTIONALLY_DIFFERENT_CONFIG_VALUE'))]:
        cfg=configparser.ConfigParser();cfg.read(LOCAL/'odoo.conf');cfg['options'].update(changes);path=LOCAL/('preflight-negative-'+label+'.conf')
        with path.open('x',encoding='utf8') as stream:cfg.write(stream)
        command=list(base);command[command.index('--odoo-config')+1]=str(path);r=subprocess.run(command,capture_output=True,timeout=60)
        assert r.returncode!=0 and b'Production preflight refused' in r.stderr;results.append(dict(case=label,refused=True,live_configuration_not_changed=True))
    environment=os.environ.copy();environment.update(MP_EXPECTED_DATABASE=state['active_db'],MP_EXPECTED_INVENTORY_DIGEST=state['inventory_digest'],MP_HTTPS_PORT='18443',MP_HTTP_PORT='18083')
    compose=subprocess.run(['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f','deploy/compose.yaml','-f','deploy/compose-production.yaml','config','--format','json'],capture_output=True,env=environment,timeout=30);assert compose.returncode==0;resolved=json.loads(compose.stdout)
    app=resolved['services']['app'];edge=resolved['services']['edge'];assert 'build' not in app and app['image']==state['image_id'] and app['command']==['-c','/run/secrets/odoo_config'] and app['read_only'] and not app.get('ports')
    assert app['environment']['MP_EXPECTED_DATABASE']==state['active_db'] and app['environment']['MP_EXPECTED_INVENTORY_DIGEST']==state['inventory_digest']
    assert all(row['host_ip']=='127.0.0.1' for row in edge['ports']) and {row['target'] for row in edge['ports']}=={8069,8443} and any(v['target']=='/etc/mp-tls' and v['read_only'] for v in edge['volumes'])
    spec=importlib.util.spec_from_file_location('mp_http_security_probe',OUTPUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);client=m.Client('production');old=(ROOT/'.local/g5-lifecycle/bootstrap-password').read_text(encoding='utf8').strip()
    for login in ['g5_alice','admin']:
        code,value,_,_=client.request('/web/session/authenticate',dict(jsonrpc='2.0',method='call',id=1,params=dict(db=state['active_db'],login=login,password=old)),headers={'Origin':client.origin})
        assert code==200 and value['error']['data']['name']=='odoo.exceptions.AccessDenied' and not value.get('result');results.append(dict(case='retired_'+login,old_credentials_refused=True))
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),positive=report,negative_cases=results,production_compose_resolved=dict(no_build=True,immutable_image=True,fixed_guarded_command=True,independent_pins=True,backend_ports_none=True,edge_loopback_by_default=True,TLS_volume_readonly=True),source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/http_profile.py','tools/production_preflight.py','deploy/compose-production.yaml','tests/test_http_profile.py']},limits=['Read-only preflight does not grant executor approval or publish an external production deployment.','Named accounts were explicitly rotated/initial accounts disabled in the owned test copy; no existing user account was changed.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',preflight_negatives=3,old_credentials_rejected=2,compose_resolved=True)))


if __name__=='__main__':main()
