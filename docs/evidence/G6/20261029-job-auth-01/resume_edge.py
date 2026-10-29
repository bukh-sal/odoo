"""Resume only the diagnosed edge step; no initialization/native replay."""
import ipaddress,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
import g6_job_fixture as j
j.select_profile('runner');f=j.f;state=f.load(j.LOCAL/'state.json');f.guard(state)
assert state['phase']=='starting_core_edge'
config=f.load(j.LOCAL/'operator/target.json')
assert 'all predefined address pools have been fully subnetted' in (j.LOCAL/'logs/start-core-edge.stderr').read_text()
counts=json.loads((j.LOCAL/'logs/reconcile-core-before-edge-02.stdout').read_bytes())
assert counts==dict(jobs=0,outbox=0,control=0,installations=0,principals=4,core='19.0.0.1.8',reference_tables_absent=True)
child=json.loads(subprocess.check_output(['docker','inspect',config['worker_id']]))[0];assert child['State']['Running']
networks=subprocess.check_output(['docker','network','ls','-q']).decode().split()
details=json.loads(subprocess.check_output(['docker','network','inspect',*networks]))
occupied=[ipaddress.ip_network(c['Subnet']) for n in details for c in (n['IPAM']['Config'] or []) if c.get('Subnet') and ':' not in c['Subnet']]
routes=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',"Get-NetRoute -AddressFamily IPv4 | Select-Object -ExpandProperty DestinationPrefix | ConvertTo-Json -Compress"]).decode('utf-8-sig'))
occupied += [ipaddress.ip_network(r) for r in routes if ipaddress.ip_network(r).prefixlen>0]
candidates=[ipaddress.ip_network('192.168.'+str(i)+'.0/28') for i in range(240,255)]
candidates += [ipaddress.ip_network('10.233.'+str(i)+'.0/28') for i in range(240,255)]
subnet=next(s for s in candidates if not any(s.overlaps(n) for n in occupied))
name=state['project']+'_edge';assert name not in [n['Name'] for n in details]
f.command('create-explicit-owned-edge',['docker','network','create','--driver','bridge','--subnet',str(subnet),'--label','com.docker.compose.project='+state['project'],'--label','com.docker.compose.network=edge','--label','com.modular.disposable='+state['project'],name])
f.command('resume-core-edge-only',['docker','compose','--env-file',str(j.LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml'),'up','-d','--no-deps','edge'])
f.phase(state,'core_only_ready');f.guard(state)
f.save('core-only-bootstrap.json',dict(result='passed',project=state['project'],configuration=config,reference_tables_absent=True,installations_empty=True,guarded_core_and_assets_ready=True))
f.save('edge-pool-reconciliation.json',dict(result='passed',diagnosis='Docker default subnet pool exhausted after completed native bootstrap. Installer subsequently refused its core_only_ready precondition, before any plan/register/apply. First read-only network-inspection helper encountered null IPAM Config on host/none networks, before creating anything; corrected normalization and fresh read-only counts retained.',observed_counts=counts,resumed_only='edge network and edge service',owned_network=name,explicit_subnet=str(subnet),existing_networks_and_host_routes_checked=True,global_Docker_configuration_changed=False,existing_networks_or_volumes_removed=False,native_init_or_provision_replayed=False))
print(json.dumps(dict(result='passed',phase=state['phase'],owned_edge_network=name)))
