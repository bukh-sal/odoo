"""Owned, phased SQL fixture for AT source probes; no existing DB is selected.

Needed to qualify real PostgreSQL primitives without replaying retired BG/AR
fixtures. The client reads current SDK source from a small read-only Linux volume.
It is not a managed application worker or attested release-image qualification.
"""
import argparse
import hashlib
import io
import ipaddress
import json
from pathlib import Path
import subprocess
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
PG='sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0'
CLIENT='sha256:a572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a'
PROBES={'partitions':'tests/native_partition_sql.py'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['prepare','run','status','retire'])
    parser.add_argument('--run',required=True);parser.add_argument('--probe',choices=PROBES,default='partitions')
    parser.add_argument('--subnet',default='10.203.158.32/28')
    args=parser.parse_args()
    if not args.run.replace('-','').isalnum() or len(args.run)>35:raise ValueError('Bounded run identity required')
    local=ROOT/'.local/aurora-tasks'/args.run;statefile=local/'state.json'

    def save(state):statefile.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8',newline='\n')

    def command(label,argv,data=None,timeout=90,allow_failure=False):
        result=subprocess.run(argv,input=data,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout)
        with (local/(label+'.log')).open('xb') as stream:stream.write(result.stdout)
        if result.returncode and not allow_failure:raise RuntimeError(label+' failed; inspect private log')
        return result

    if args.phase=='prepare':
        local.mkdir(parents=True,exist_ok=False);name='mp-at-'+args.run;label='com.modular.disposable='+name
        state=dict(phase='allocating',name=name,probe=args.probe,network=name+'-net',db=name+'-db',source=name+'-source',data=name+'-data')
        save(state)
        subnet=ipaddress.ip_network(args.subnet,strict=True)
        if not subnet.is_private or subnet.version!=4 or subnet.prefixlen!=28:raise ValueError('Private /28 required')
        ids=command('network-inventory',['docker','network','ls','-q']).stdout.decode().split()
        networks=json.loads(command('network-addresses',['docker','network','inspect',*ids]).stdout)
        if any(subnet.overlaps(ipaddress.ip_network(c['Subnet'])) for n in networks
               for c in n.get('IPAM',{}).get('Config') or [] if c.get('Subnet')):raise ValueError('Network overlaps existing target')
        command('create-network',['docker','network','create','--internal','--subnet',str(subnet),'--label',label,state['network']])
        for key in ('source','data'):command('create-'+key,['docker','volume','create','--label',label,state[key]])
        command('start-db',['docker','run','-d','--name',state['db'],'--label',label,'--network',state['network'],
            '--network-alias','db','--memory','512m','--pids-limit','128','--env','POSTGRES_HOST_AUTH_METHOD=trust',
            '--mount','type=volume,source='+state['data']+',target=/var/lib/postgresql/data',PG])
        for _ in range(45):
            if subprocess.run(['docker','exec',state['db'],'pg_isready','-U','postgres'],capture_output=True).returncode==0:break
            time.sleep(1)
        else:raise RuntimeError('Database readiness not observed; inspect existing target')
        command('create-probe-db',['docker','exec',state['db'],'createdb','-U','postgres','at_partition_probe'])
        paths=[p for folder in ('packages/platform_sdk/modular_platform','packages/contracts')
               for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc']
        paths += [ROOT/PROBES[args.probe],ROOT/'tests/background_postgres.py']
        hashes={};stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as archive:
            for path in sorted(paths):
                assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
                raw=path.read_bytes();relative=path.relative_to(ROOT).as_posix();hashes[relative]=hashlib.sha256(raw).hexdigest()
                entry=tarfile.TarInfo(relative);entry.size=len(raw);entry.mode=0o444
                archive.addfile(entry,io.BytesIO(raw))
        state['source_sha256']=hashes;state['subnet']=str(subnet);save(state)
        command('stage-source',['docker','run','--rm','-i','--name',name+'-stage','--label',label,'--network','none',
            '--user','0:0','--cap-drop','ALL','--mount','type=volume,source='+state['source']+',target=/probe',
            '--entrypoint','/venv/bin/python',CLIENT,'-c',
            "import sys,tarfile;tarfile.open(fileobj=sys.stdin.buffer,mode='r|*').extractall('/probe',filter='data')"],stream.getvalue())
        state['phase']='prepared';save(state)
    else:
        state=json.loads(statefile.read_bytes());label='com.modular.disposable='+state['name']
        if args.phase=='run':
            if state['phase']!='prepared':raise ValueError('Inspect existing run; never replay an uncertain mutation')
            state['phase']='running';save(state)
            result=command('probe',['docker','run','--rm','--name',state['name']+'-probe','--label',label,
                '--network',state['network'],'--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                '--memory','768m','--pids-limit','128','--tmpfs','/tmp','--env','PYTHONPATH=/probe/packages/platform_sdk:/probe/tests',
                '--mount','type=volume,source='+state['source']+',target=/probe,readonly',
                '--entrypoint','/venv/bin/python',CLIENT,'/probe/'+PROBES[state['probe']]],allow_failure=True)
            rows=[json.loads(line.split('=',1)[1]) for line in result.stdout.decode().splitlines() if line.startswith('MP_AT_SQL=')]
            state['phase']='passed' if result.returncode==0 and len(rows)==1 else 'failed'
            state['exit_code']=result.returncode
            if rows:state['result']=rows[-1]
            save(state)
            if state['phase']=='failed':raise RuntimeError('SQL probe failed; inspect existing private log')
        elif args.phase=='retire':
            if state['phase'] not in ('passed','failed'):raise ValueError('Inspect live or incomplete run before retirement')
            name='mp-at-'+args.run
            if any(state[key]!=name+suffix for key,suffix in [('name',''),('db','-db'),('network','-net'),('source','-source'),('data','-data')]):
                raise ValueError('Exact owned target identity required')
            for kind,key in [('container','db'),('network','network'),('volume','source'),('volume','data')]:
                item=json.loads(command('retire-inspect-'+key,['docker',kind,'inspect',state[key]]).stdout)[0]
                labels=item['Config']['Labels'] if kind=='container' else item['Labels']
                if labels.get('com.modular.disposable')!=state['name']:raise ValueError('Ownership mismatch')
            command('retire-db',['docker','rm','-f',state['db']])
            for key in ('source','data'):command('retire-'+key,['docker','volume','rm',state[key]])
            command('retire-network',['docker','network','rm',state['network']])
            state['phase']='retired';save(state)
    print(json.dumps({key:state[key] for key in ('phase','name','result') if key in state}))


if __name__=='__main__':main()
