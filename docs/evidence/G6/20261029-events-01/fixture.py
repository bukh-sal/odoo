"""Fresh owned event integration site; all prior queues remain untouched."""
import argparse,base64,hashlib,ipaddress,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_fixture as f
from modular_platform.catalog import Catalog
from modular import configuration
f.LOCAL=LOCAL=ROOT/'.local/g6-events';f.OUTPUT=OUTPUT=Path(__file__).resolve().parent/'site'
f.PROTECTED=[*f.PROTECTED,'.local/g6/operator/target.json','.local/g6-jobs/operator/target.json','.local/g6-jobs-runner/operator/target.json']


def curate(build,runtime,project):
    assert runtime['platform_version']=='0.1.9' and runtime['native_manifests']['mp_shell']['version']=='19.0.0.1.8'
    artifacts={name:build['artifacts'][name] for name in ['org.example.notes','org.example.notes_labels']}
    assert artifacts['org.example.notes']['version']=='0.2.6' and artifacts['org.example.notes_labels']['version']=='0.2.3'
    source="import base64,json,pathlib;names="+repr({name:item['file'] for name,item in artifacts.items()})+";print(json.dumps({name:base64.b64encode((pathlib.Path('/opt/modular/artifacts')/file).read_bytes()).decode() for name,file in names.items()}))"
    raw=f.command('extract-event-artifacts',['docker','run','--name',project+'-extract-event-artifacts','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--entrypoint','/venv/bin/python',build['image_id'],'-c',source])
    values=json.loads(raw);paths={}
    for name,item in artifacts.items():
        data=base64.b64decode(values[name]);assert 'sha256:'+hashlib.sha256(data).hexdigest()==item['digest']
        path=LOCAL/item['file'];assert not path.exists();path.write_bytes(data);paths[name]=path
    policy=f.load(LOCAL/'operator/trust.json');assert policy['generation']==3;policy['generation']=4
    policy['approved_digests'] += [item['digest'] for item in artifacts.values()];f.write(LOCAL/'operator/trust.json',policy)
    catalog=Catalog(LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json'));assert len(catalog.snapshot())==7
    for name,item in artifacts.items():catalog.add(paths[name],expected_digest=item['digest'])
    assert len(catalog.snapshot())==9
    f.save('isolated-curation.json',dict(result='passed',artifacts=artifacts,trust_generation=4,catalog_entries=9,global_catalog_and_trust_unchanged=True))


def networks(state):
    # Docker's default subnet pool was exhausted on the preceding owned fixture.
    # Select small disjoint project-only subnets; never prune/reconfigure others.
    names=subprocess.check_output(['docker','network','ls','-q']).decode().split()
    details=json.loads(subprocess.check_output(['docker','network','inspect',*names]))
    occupied=[ipaddress.ip_network(c['Subnet']) for n in details for c in (n['IPAM']['Config'] or []) if c.get('Subnet') and ':' not in c['Subnet']]
    routes=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command','Get-NetRoute -AddressFamily IPv4 | Select-Object -ExpandProperty DestinationPrefix | ConvertTo-Json -Compress']).decode('utf-8-sig'))
    occupied += [ipaddress.ip_network(route) for route in routes if ipaddress.ip_network(route).prefixlen>0]
    candidates=[ipaddress.ip_network('192.168.'+str(third)+'.'+str(fourth)+'/28') for third in range(240,255) for fourth in range(0,256,16)]
    candidates += [ipaddress.ip_network('10.233.'+str(third)+'.'+str(fourth)+'/28') for third in range(240,255) for fourth in range(0,256,16)]
    selected={}
    for group in ['runtime','edge']:
        name=state['project']+'_'+group;assert name not in [n['Name'] for n in details]
        subnet=next(net for net in candidates if not any(net.overlaps(old) for old in occupied));occupied.append(subnet)
        arguments=['docker','network','create','--driver','bridge','--subnet',str(subnet),'--label','com.docker.compose.project='+state['project'],'--label','com.docker.compose.network='+group,'--label','com.modular.disposable='+state['project']]
        if group=='runtime':arguments.append('--internal')
        f.command('create-owned-'+group+'-network',arguments+[name]);selected[group]=dict(name=name,subnet=str(subnet),internal=group=='runtime')
    f.save('owned-networks.json',dict(result='passed',networks=selected,existing_Docker_and_host_routes_checked=True,global_configuration_changed=False,existing_networks_or_volumes_removed=False))


def enable():
    state=f.load(LOCAL/'state.json');f.guard(state);assert state['phase']=='references_installed'
    code="""import json
from modular_platform import durable
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.site_id'");site=env.cr.fetchone()[0]
env.cr.execute("SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'");release=env.cr.fetchone()[0]
env.cr.execute('SELECT count(*) FROM mp_job');assert env.cr.fetchone()[0]==0
env.cr.execute('SELECT count(*) FROM mp_outbox');assert env.cr.fetchone()[0]==0
durable.set_control(env.cr,site,release,'enabled');env.cr.commit();print('MP_EVENT_ENABLE='+json.dumps(dict(enabled=True)))
"""
    raw=f.native(state,'enable-event-fixture',[],code);assert 'MP_EVENT_ENABLE={"enabled": true}' in raw.decode()
    f.phase(state,'event_fixture_ready');f.guard(state)
    f.save('fixture-dispatch-enable.json',dict(result='passed',explicit_OS_fixture_bootstrap=True,initial_jobs_and_events_zero=True,no_claim_of_generic_populated_queue_lifecycle=True))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['configure','networks','initialize','install','enable']);args=parser.parse_args()
    if args.action=='configure':
        f.configure(build_path=ROOT/'docs/evidence/G6/20261029-events-candidate-01/candidate-build.json',core_version='19.0.0.1.9',hostname='g6events.localhost',port_start=18088,curator=curate)
        networks(f.load(LOCAL/'state.json'))
    elif args.action=='enable':enable()
    elif args.action=='networks':
        state=f.load(LOCAL/'state.json');f.guard(state);assert state['phase']=='configured'
        networks(state)
    else:getattr(f,args.action)()


if __name__=='__main__':main()
