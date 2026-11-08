"""AT-01 disposable native authority feasibility; explicit phases, no resets.

Runs core47 with four inventoried draft source overlays on an owned Linux volume.
This is a feasibility environment, never an attested release build or deployment.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import secrets
import subprocess
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:a572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a'
POSTGRES = 'sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'
OVERLAYS = {
    'framework_addons/mp_core/async_models.py':'addons/mp_core/async_models.py',
    'framework_addons/mp_core/job_dispatch.py':'addons/mp_core/job_dispatch.py',
    'framework_addons/mp_core/native_jobs.py':'addons/mp_core/native_jobs.py',
    'packages/platform_sdk/modular_platform/durable.py':'packages/platform_sdk/modular_platform/durable.py',
    'tests/aurora_native_job_probe_body.py':'native_probe.py',
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','initialize','probe','status','retire'])
    parser.add_argument('--run',required=True)
    parser.add_argument('--subnet',default='10.203.158.0/28')
    args=parser.parse_args()
    if not args.run.replace('-','').isalnum() or len(args.run)>35:raise ValueError('Bounded run identity required')
    local=ROOT/'.local/aurora-tasks'/args.run
    statefile=local/'state.json'

    def save(state):
        statefile.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8',newline='\n')

    def command(label,argv,data=None,timeout=120):
        # All command output is private; never echo credentials/native tracebacks.
        result=subprocess.run(argv,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        log=local/(label+'.log')
        with log.open('xb') as stream:stream.write(result.stdout)
        if result.returncode:raise RuntimeError(label+' failed; inspect private log before any retry')
        return result.stdout

    if args.phase=='prepare':
        local.mkdir(parents=True,exist_ok=False)
        name='mp-at-'+args.run
        state=dict(phase='allocating',name=name,image=IMAGE,postgres=POSTGRES,network=name+'-net',
                   db=name+'-db',volumes=[name+'-source',name+'-data',name+'-files'],database='at_native_probe',
                   source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in OVERLAYS})
        save(state)
        label='com.modular.disposable='+name
        command('image-inspect',['docker','image','inspect',IMAGE,POSTGRES])
        subnet=ipaddress.ip_network(args.subnet,strict=True)
        if not subnet.is_private or subnet.version!=4 or subnet.prefixlen!=28:
            raise ValueError('Explicit private /28 probe network required')
        names=command('network-inventory',['docker','network','ls','-q']).decode().split()
        networks=json.loads(command('network-addresses',['docker','network','inspect',*names]))
        for network in networks:
            for config in network.get('IPAM',{}).get('Config') or []:
                if config.get('Subnet') and subnet.overlaps(ipaddress.ip_network(config['Subnet'])):
                    raise ValueError('Selected probe subnet overlaps an existing network')
        state['subnet']=str(subnet);save(state)
        command('create-network',['docker','network','create','--internal','--subnet',str(subnet),'--label',label,state['network']])
        for index,volume in enumerate(state['volumes']):
            command('create-volume-'+str(index),['docker','volume','create','--label',label,volume])
        envfile=local/'db.env'
        envfile.write_text('POSTGRES_PASSWORD='+secrets.token_hex(24)+'\n',encoding='utf8',newline='\n')
        command('start-db',['docker','run','-d','--name',state['db'],'--label',label,
            '--network',state['network'],'--network-alias','db','--env-file',str(envfile),
            '--mount','type=volume,source='+state['volumes'][1]+',target=/var/lib/postgresql/data',POSTGRES])
        for attempt in range(45):
            ready=subprocess.run(['docker','exec',state['db'],'pg_isready','-U','postgres'],capture_output=True)
            if ready.returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('Database readiness not observed; inspect existing target')
        password=secrets.token_hex(24)
        command('create-native-probe-db',['docker','exec','-i',state['db'],'psql','-U','postgres','-v','ON_ERROR_STOP=1'],
            ("CREATE ROLE modular LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '"+password+"';\n"
             "CREATE DATABASE at_native_probe OWNER modular;\n").encode())
        command('copy-owned-source',['docker','run','--rm','--name',name+'-copy','--label',label,
            '--network','none','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN',
            '--mount','type=volume,source='+state['volumes'][0]+',target=/fixture',
            '--mount','type=volume,source='+state['volumes'][2]+',target=/files',
            '--entrypoint','/venv/bin/python',IMAGE,'-c',
            "import shutil,os;shutil.copytree('/opt/modular','/fixture',dirs_exist_ok=True);os.chown('/files',10001,10001)"])
        files={target:(ROOT/source).read_bytes() for source,target in OVERLAYS.items()}
        files['probe.cfg']=('[options]\naddons_path=/opt/modular/addons,/opt/modular/odoo/addons\n'
            'data_dir=/var/lib/modular\ndb_host=db\ndb_port=5432\ndb_user=modular\ndb_password='+password+
            '\ndb_name=at_native_probe\nlist_db=False\nhttp_enable=False\nmax_cron_threads=0\nworkers=0\n').encode()
        # Existing successful packaging probe supplies a real non-example manifest.
        import zipfile
        with zipfile.ZipFile(ROOT/'.local/aurora-tasks/at01-native-package.mplug') as archive:
            files['probe_plugin.toml']=archive.read('dev.aurora.tasks/plugin.toml')
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for path,raw in sorted(files.items()):
                entry=tarfile.TarInfo(path);entry.size=len(raw);entry.mode=0o444
                archive.addfile(entry,io.BytesIO(raw))
        command('overlay-source',['docker','run','--rm','-i','--name',name+'-overlay','--label',label,
            '--network','none','--user','0:0','--cap-drop','ALL',
            '--mount','type=volume,source='+state['volumes'][0]+',target=/fixture',
            '--entrypoint','/venv/bin/python',IMAGE,'-c',
            "import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|*').extractall('/fixture',filter='data')"],
            stream.getvalue())
        state['phase']='prepared';save(state)
    else:
        state=json.loads(statefile.read_bytes())
        if args.phase in ('initialize','probe'):
            required='prepared' if args.phase=='initialize' else 'initialized'
            if state['phase']!=required:raise ValueError('Wrong phase; inspect journal, do not replay mutation')
            state['phase']=args.phase+'_started';save(state)
            label='com.modular.disposable='+state['name']
            argv=['docker','run','--rm','-i','--name',state['name']+'-'+args.phase,'--label',label,
                '--network',state['network'],'--read-only','--cap-drop','ALL',
                '--security-opt','no-new-privileges','--memory','1536m','--pids-limit','128','--tmpfs','/tmp',
                '--mount','type=volume,source='+state['volumes'][0]+',target=/opt/modular,readonly',
                '--mount','type=volume,source='+state['volumes'][2]+',target=/var/lib/modular',
                '--entrypoint','/venv/bin/python',IMAGE]
            if args.phase=='probe':argv+=['odoo-bin','shell']
            else:argv+=['odoo-bin']
            argv+=['-c','/opt/modular/probe.cfg','-d',state['database'],'--no-http','--workers=0','--max-cron-threads=0']
            if args.phase=='initialize':argv+=['-i','mp_core,mp_aurora_tasks','--stop-after-init','--without-demo','all']
            raw=command(args.phase,argv,b"exec(open('/opt/modular/native_probe.py').read())\n" if args.phase=='probe' else None,timeout=300)
            if args.phase=='probe':
                rows=[json.loads(line.split('=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_AT_NATIVE=')]
                if len(rows)!=1:raise RuntimeError('No unique probe result; inspect existing DB before retry')
                state['probe_result']=rows[0]
            state['phase']='initialized' if args.phase=='initialize' else 'probed';save(state)
        elif args.phase=='retire':
            if state['phase']!='probed':raise ValueError('Inspect incomplete operations before retirement')
            if (state['name']!='mp-at-'+args.run or state['db']!=state['name']+'-db'
                    or state['network']!=state['name']+'-net'
                    or state['volumes']!=[state['name']+'-'+suffix for suffix in ('source','data','files')]):
                raise ValueError('Recorded targets differ from this exact owned probe')
            expected=state['name']
            for kind,target in [('container',state['db']),('network',state['network'])]+[('volume',v) for v in state['volumes']]:
                info=json.loads(command('retire-inspect-'+target,['docker',kind,'inspect',target]))[0]
                labels=info.get('Labels',{}) if kind!='container' else info['Config']['Labels']
                if labels.get('com.modular.disposable')!=expected:raise ValueError('Ownership mismatch')
            command('retire-db',['docker','rm','-f',state['db']])
            for volume in state['volumes']:command('retire-'+volume,['docker','volume','rm',volume])
            command('retire-network',['docker','network','rm',state['network']])
            state['phase']='retired';state['retired_utc']=datetime.now(timezone.utc).isoformat();save(state)
    print(json.dumps({k:v for k,v in state.items() if k in ('phase','name','probe_result','source_sha256')}))


if __name__=='__main__':main()
