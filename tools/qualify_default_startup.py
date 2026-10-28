"""Once-only default-entrypoint probes on a fresh, retained disposable DB clone.

No live application mutation/deployment, exposed port, cron, approval mount or
Docker socket. Probe configuration is copied inside Docker, never printed.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import _write_new
from modular_platform.plans import data_digest
from modular import configuration


def command(args,*,input=None,timeout=90):
    result=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError('Startup qualification command failed (diagnostics withheld): '+args[0])
    return result.stdout


SEED="""import configparser,json,os,pathlib,sys
data=json.load(sys.stdin);base=pathlib.Path('/probe')
for case,changes in data['configs'].items():
 config=configparser.ConfigParser();config.read('/source/odoo_config');config['options']['db_name']=data['database']
 config['options'].update(changes);folder=base/'config'/case;folder.mkdir(parents=True)
 with (folder/'odoo_config').open('w') as stream:config.write(stream)
 (base/'data'/case).mkdir(parents=True)
for case,name,content in data['extra']:
 folder=base/'addon'/case;folder.mkdir(parents=True)
 if case=='source_symlink':(folder/name).symlink_to('/opt/modular/addons/mp_example_notes/__manifest__.py')
 else:(folder/name).write_text(content)
for case in ['data_addon','data_symlink']:
 folder=base/'data'/case/'addons/19.0';folder.mkdir(parents=True)
 if case=='data_symlink':(folder/'injected').symlink_to('/opt/modular/addons/mp_example_notes',target_is_directory=True)
 else:(folder/'injected.py').write_text("raise RuntimeError('MUST_NOT_IMPORT')")
for folder in base.rglob('*'):
 if not folder.is_symlink():
  folder.chmod(0o755 if folder.is_dir() else 0o444)
  if folder.relative_to(base).parts[0]=='data':os.chown(folder,10001,10001)
"""


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--image-id',required=True)
    parser.add_argument('--resume-negative-qualified',action='store_true',help='Resume retained clone after the recorded dump-order harness failure; never recreate/reprobe')
    args=parser.parse_args();output=args.output.resolve()
    private=protect_directory(ROOT/'.local/g5/startup-probes');marker=private/(output.name+'.json')
    resume=args.resume_negative_qualified
    if not output.is_relative_to(ROOT/'docs/evidence/G5') or (not resume and (output.exists() or marker.exists())):
        raise ValueError('Fresh once-only G5 startup evidence required; inspect previous marker before retrying')
    target=json.loads((ROOT/'.local/operator/targets/g5.json').read_text())
    if target['project']!='mp-r0-r1g5fd0445d406d6':raise ValueError('Exact named disposable target required')
    catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    observer=DockerObserver(target);before=observer.state(observer.read(),catalog)['state']
    runtime=inspect_image(args.image_id);pin=runtime['inventory_digest']
    entry=json.loads(command(['docker','image','inspect',args.image_id,'--format','{{json .Config.Entrypoint}}']))
    assert entry==['/venv/bin/python','/opt/modular/tools/start_worker.py']
    assert command(['docker','run','--rm','--network','none','--entrypoint','/bin/cat',args.image_id,'/opt/modular/startup-profile']).strip()==b'r1'
    saved=json.loads(marker.read_text()) if resume else None
    if resume and (saved['state']!='prepared' or saved['image_id']!=args.image_id or not (output/'postnegative-harness-failure.json').is_file()):
        raise ValueError('Only the exact negative-qualified dump-order failure can resume')
    token=saved['database'].removeprefix('mp_disposable_r0_r1_boot_') if resume else uuid4().hex[:16]
    if not re.fullmatch('[0-9a-f]{16}',token):raise ValueError('Exact disposable probe identity required')
    database='mp_disposable_r0_r1_boot_'+token;volume='mp-r1-startup-'+token
    db_container=observer._container('db');network=target['project']+'_runtime'
    if not resume:output.mkdir(parents=True)
    record={'state':'preparing','database':database,'volume':volume,'image_id':args.image_id,
        'source_database':target['sites'][0]['database'],'evidence':str(output.relative_to(ROOT))}
    if not resume:_write_new(marker,record)

    def sql(statement,db=database):
        return command(['docker','exec','-i',db_container,'psql','-X','-qAt','-U','postgres',
            '-v','ON_ERROR_STOP=1','-d',db],input=statement.encode())

    def dump(db=database):
        raw=command(['docker','exec',db_container,'pg_dump','-U','postgres','--no-owner','--no-privileges','--no-comments',db],timeout=120)
        # PG security restrict tokens are randomized and are not database state.
        lines=[];rows=None
        for line in raw.splitlines():
            if line.startswith((b'\\restrict ',b'\\unrestrict ')):continue
            if rows is not None:
                if line==b'\\.':lines.extend(sorted(rows));lines.append(line);rows=None
                else:rows.append(line)
            else:
                lines.append(line)
                if line.startswith(b'COPY ') and line.endswith(b' FROM stdin;'):rows=[]
        assert rows is None,'Truncated database dump'
        return b'\n'.join(lines)

    owner=sql('SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=current_database();',target['sites'][0]['database']).decode().strip()
    if not re.fullmatch('[a-z_][a-z0-9_]*',owner):raise ValueError('Unexpected disposable DB owner')
    if not resume:
        archive=command(['docker','exec',db_container,'pg_dump','-U','postgres','-Fc',target['sites'][0]['database']],timeout=120)
        command(['docker','exec',db_container,'createdb','-U','postgres','-T','template0','-O',owner,database])
        command(['docker','exec','-i',db_container,'pg_restore','-U','postgres','--exit-on-error','--no-owner','--role',owner,'-d',database],input=archive,timeout=120)
        sql("UPDATE ir_config_parameter SET value='"+pin+"' WHERE key='mp.active_inventory_digest';")
    # This clone is a startup fixture, never published/operated as a platform
    # release. Its other publication metadata remains an explicitly stale copy.
    configs={name:{} for name in ['valid','missing_db','missing_pin','wrong_pin','wrong_db','database_pin','extra_source',
        'extra_bytecode','extra_cache','source_symlink','data_addon','data_symlink','pending_install','pending_upgrade',
        'pending_remove','wrong_version','cli_init','cli_update','cli_reinit','cli_pre_upgrade','bootstrap_source']}
    for key,value in [('init','base'),('update','all'),('reinit','base'),('pre_upgrade_scripts','/tmp/probe.py'),('upgrade_path','/tmp')]:
        configs['config_'+key]={key:value}
    extra=[('extra_source','__init__.py',"raise RuntimeError('MUST_NOT_IMPORT')"),('extra_bytecode','injected.pyc','unknown'),
        ('extra_cache','injected.cpython-312.pyc','unknown'),('source_symlink','alias.py',''),('bootstrap_source','worker_start.py',"raise RuntimeError('MUST_NOT_IMPORT')")]
    if not resume:
        command(['docker','volume','create','--label','modular.disposable=startup-qualification',volume])
        command(['docker','run','--rm','-i','--network','none','--user','0:0','--read-only','--cap-drop','ALL','--cap-add','CHOWN',
            '--mount','type=volume,source='+target['project']+'_appconfig,target=/source,readonly',
            '--mount','type=volume,source='+volume+',target=/probe','--entrypoint','/venv/bin/python',args.image_id,'-c',SEED],
            input=json.dumps({'configs':configs,'extra':extra,'database':database}).encode())
        record['state']='prepared';marker.write_text(json.dumps(record,indent=2)+'\n')
    clone_before=dump();cases=json.loads((output/'negative-cases.json').read_text()) if resume else []
    if resume:
        assert {row['case'] for row in cases}==set(configs)-{'valid'} and all(row['database_unchanged'] for row in cases)
        assert sql("SELECT value FROM ir_config_parameter WHERE key='mp.active_inventory_digest';").decode().strip()==pin
        assert sql("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove');").strip()==b'0'
        (output/'negative-reconciliation.json').write_text(json.dumps({'result':'resumed_existing_clone','negative_cases':len(cases),
            'clone_not_recreated':True,'negative_probes_not_repeated':True,'comparison':'COPY row order canonicalized; schema/sequences/row bytes retained'},indent=2)+'\n')

    def invocation(case):
        name='mp-r1-startup-'+token+'-'+case.replace('_','-')
        cmd=['docker','run','--name',name,'--read-only','--user','10001:10001','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--network',network,'--pids-limit','256','--memory','768m','--cpus','2',
            '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777',
            '--mount','type=volume,source='+volume+',target=/run/secrets,volume-subpath=config/'+case+',readonly',
            '--mount','type=volume,source='+volume+',target=/var/lib/modular,volume-subpath=data/'+case]
        if case!='missing_db':cmd+=['-e','MP_EXPECTED_DATABASE='+('wrong_database' if case=='wrong_db' else database)]
        if case!='missing_pin':cmd+=['-e','MP_EXPECTED_INVENTORY_DIGEST='+('sha256:'+'0'*64 if case=='wrong_pin' else pin)]
        if case in {'extra_source','extra_bytecode','extra_cache','source_symlink','bootstrap_source'}:
            destination='/opt/modular/packages/platform_sdk/modular_platform' if case=='bootstrap_source' else (
                '/opt/modular/addons/mp_example_notes/__pycache__' if case=='extra_cache' else '/opt/modular/addons/mp_boot_probe')
            cmd+=['--mount','type=volume,source='+volume+',target='+destination+',volume-subpath=addon/'+case+',readonly']
        return name,cmd

    for case in ([] if resume else configs):
        if case=='valid':continue
        original=None
        if case.startswith('pending_') or case=='wrong_version':
            original=json.loads(sql("SELECT jsonb_build_array(state,latest_version) FROM ir_module_module WHERE name='mp_example_notes';"))
            change="latest_version='19.0.0.0.0'" if case=='wrong_version' else "state='"+{'pending_install':'to install','pending_upgrade':'to upgrade','pending_remove':'to remove'}[case]+"'"
            sql("UPDATE ir_module_module SET "+change+" WHERE name='mp_example_notes';")
        if case=='database_pin':sql("UPDATE ir_config_parameter SET value='sha256:"+'0'*64+"' WHERE key='mp.active_inventory_digest';")
        baseline=dump();name,cmd=invocation(case)
        native_args=['-c','/run/secrets/odoo_config']
        if case.startswith('cli_'):native_args+=[{'cli_init':'-i','cli_update':'-u','cli_reinit':'--reinit','cli_pre_upgrade':'--pre-upgrade-scripts'}[case],'base']
        result=subprocess.run(cmd+[args.image_id,*native_args],capture_output=True,timeout=90)
        text=(result.stdout+result.stderr).decode(errors='replace')
        message=('pins are required' if case in {'missing_db','missing_pin'} else 'inventory pin mismatch' if case=='wrong_pin' else
            'bootstrap configuration' if case=='wrong_db' or case.startswith('config_') else 'fixed configuration' if case.startswith('cli_') else
            'Database release inventory differs' if case=='database_pin' else 'never performs migration' if original else
            'bootstrap source differs' if case=='bootstrap_source' else 'source symlink' if case=='source_symlink' else
            'writable data-dir' if case.startswith('data_') else 'search-path content')
        assert result.returncode!=0 and message in text and 'MUST_NOT_IMPORT' not in text,(case,'incorrect denial boundary')
        assert dump()==baseline,(case,'database changed during denied boot')
        cases.append({'case':case,'result':'denied_before_native_import','expected_error':message,'database_unchanged':True,'container':name})
        if original:sql("UPDATE ir_module_module SET state='"+original[0]+"',latest_version='"+original[1]+"' WHERE name='mp_example_notes';")
        if case=='database_pin':sql("UPDATE ir_config_parameter SET value='"+pin+"' WHERE key='mp.active_inventory_digest';")
        (output/'negative-cases.json').write_text(json.dumps(cases,indent=2)+'\n')
        print(json.dumps({'case':case,'result':'passed'}),flush=True)
    assert dump()==clone_before
    name,cmd=invocation('valid');command(cmd[:2]+['-d']+cmd[2:]+[args.image_id])
    record.update(state='positive_running',container=name);marker.write_text(json.dumps(record,indent=2)+'\n')
    health="import urllib.request; r=urllib.request.urlopen('http://"+name+":8069/web/health',timeout=4); assert r.status==200; print('ready')"
    try:
        ready=False
        for attempt in range(30):
            result=subprocess.run(['docker','exec',observer._container('app'),'/venv/bin/python','-c',health],capture_output=True,timeout=10)
            if result.returncode==0:ready=True;break
            if not json.loads(command(['docker','inspect',name,'--format','{{json .State.Running}}'])):break
            time.sleep(1)
        assert ready,'Compatible default boot did not become ready (inspect retained private container logs)'
        source=command(['docker','exec',name,'/venv/bin/python','-c',__import__('modular_platform.deployment',fromlist=['OBSERVE_RUNTIME']).OBSERVE_RUNTIME])
        checked=json.loads(source);assert not any(checked[key] for key in ['modified_files','unexpected_addon_files','missing_addon_files'])
    finally:command(['docker','stop','--time','15',name])
    assert dump()==clone_before,'Compatible startup changed database schema or contents'
    assert observer.state(observer.read(),catalog)['state']==before,'Live deployment changed during isolated probes'
    paths=['deploy/Dockerfile','tools/start_worker.py','tools/qualify_default_startup.py',
        'packages/platform_sdk/modular_platform/worker_start.py','packages/platform_sdk/modular_platform/deployment.py']
    report={'result':'passed','utc':datetime.now(timezone.utc).isoformat(),'image_id':args.image_id,'inventory_digest':pin,
        'database':database,'disposable':True,'negative_cases':len(cases),'compatible_default_boot':True,
        'clone_database_unchanged':True,'clone_schema_data_sha256':hashlib.sha256(clone_before).hexdigest(),
        'source_unchanged':True,'live_deployment_state_unchanged':True,'live_state_digest':data_digest(before),
        'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},
        'limits':['Clone publication metadata intentionally stale except candidate inventory; no app release/deployment claimed.',
            'No default-start command is a sandbox for trusted native plugins or a Docker operator.',
            'Fresh-release install, skipped migration, uninstall and full G5 qualification remain separate checks.'],
        'retained':{'database':database,'volume':volume,'positive_container':name,'negative_containers':[case['container'] for case in cases]}}
    (output/'default-startup.json').write_text(json.dumps(report,indent=2)+'\n')
    record['state']='qualified';marker.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'result':'passed','negative_cases':len(cases),'evidence':str(output.relative_to(ROOT))}))


if __name__=='__main__':main()
