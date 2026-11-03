"""Retire only exact newly owned completed HTTP qualification targets."""
import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-production-profile-01'
load=lambda p:json.loads(p.read_text());s=load(LOCAL/'state.json');assert load(OUT/'qualification.json')['result']=='passed_current_SEC02_SEC04_and_selected_proxy_profiles'
assert s['phase']=='profiles_started_ready';project=s['project'];assert project=='mp-r0-r1g7httpef5ead610623' and s['disposable']
containers=[e['container_id'] for e in s['containers']]+[s['db_container']]
def run(label,args,timeout=60):
 r=subprocess.run(args,capture_output=True,timeout=timeout);(LOCAL/('retire-'+label+'.stdout')).write_bytes(r.stdout);(LOCAL/('retire-'+label+'.stderr')).write_bytes(r.stderr);assert r.returncode==0,'Inspect retained exact retirement state before continuing'
 return r.stdout
observed=json.loads(run('observe',['docker','inspect',*containers]));assert len(observed)==4
for row in observed:
 assert row['Name'].startswith('/'+project+'-') and (row['Config']['Labels'].get('com.docker.compose.project')==project or row['Config']['Labels'].get('com.modular.qualification')=='G7-production-profile')
volumes=subprocess.check_output(['docker','volume','ls','-q']).decode().split();volumes=[v for v in volumes if v.startswith(project+'_')];assert set(volumes)=={project+'_'+v for v in ['pgdata','filestore','appconfig','dbconfig','bootstrap','evidence','proxyconfig','prodproxy','tls']}
# Compose creates pgdata/filestore plus five seeded configs and prodproxy/TLS:
# nine volumes, not the earlier rough eight. Preserve actual observation.
vmeta=json.loads(run('volumes',['docker','volume','inspect',*volumes]))
for row in vmeta:
 labels=row['Labels'] or {};assert labels.get('com.docker.compose.project')==project or labels.get('com.modular.disposable')==project or labels.get('com.modular.qualification')=='G7-production-profile'
networks=[project+'_runtime',project+'_edge'];nmeta=json.loads(run('networks',['docker','network','inspect',*networks]));assert all(row['Labels'].get('com.modular.disposable')==project for row in nmeta)
(LOCAL/'retirement-intent.json').write_text(json.dumps(dict(containers=containers,volumes=volumes,networks=networks),indent=2))
for entry in s['containers']:
 run('logs-'+entry['purpose'],['docker','logs',entry['container_id']]);run('stop-'+entry['purpose'],['docker','stop','--time','15',entry['container_id']],timeout=40)
s.update(phase='qualified_fixture_app_edges_stopped');(LOCAL/'state.json').write_text(json.dumps(s,indent=2))
with (LOCAL/'retired-fixture.dump').open('xb') as output:
 r=subprocess.run(['docker','exec',s['db_container'],'pg_dump','-U','postgres','--no-owner','-Fc',s['active_db']],stdout=output,stderr=subprocess.PIPE,timeout=60);(LOCAL/'retire-dump.stderr').write_bytes(r.stderr);assert r.returncode==0
code="import sys,tarfile;t=tarfile.open(fileobj=sys.stdout.buffer,mode='w|');t.add('/data',arcname='data');t.close()"
with (LOCAL/'retired-filestore.tar').open('xb') as output:
 r=subprocess.run(['docker','run','--rm','--name','mp-g7-http-retirement-filestore','--label','com.modular.disposable='+project,'--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--mount','type=volume,source='+project+'_filestore,target=/data,readonly','--entrypoint','/venv/bin/python',s['image_id'],'-c',code],stdout=output,stderr=subprocess.PIPE,timeout=60);(LOCAL/'retire-filestore.stderr').write_bytes(r.stderr);assert r.returncode==0
run('stop-db',['docker','stop','--time','15',s['db_container']],timeout=40)
after=json.loads(run('stopped',['docker','inspect',*containers]));assert all(not r['State']['Running'] for r in after)
for row in after:run('remove-'+row['Id'][:12],['docker','rm',row['Id']])
for volume in volumes:
 assert not subprocess.check_output(['docker','ps','-aq','--filter','volume='+volume]).strip();run('volume-'+volume.split('_')[-1],['docker','volume','rm',volume])
for network in networks:
 info=json.loads(subprocess.check_output(['docker','network','inspect',network]))[0];assert not info['Containers'];run('network-'+network.split('_')[-1],['docker','network','rm',network])
archives={name:dict(bytes=(LOCAL/name).stat().st_size,sha256=hashlib.sha256((LOCAL/name).read_bytes()).hexdigest()) for name in ['retired-fixture.dump','retired-filestore.tar']}
s.update(phase='qualified_fixture_archived_and_retired',retired_utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(s,indent=2))
record=dict(result='exact_completed_owned_fixture_archived_and_retired',utc=s['retired_utc'],project=project,containers_removed=[r['Id'] for r in after],volumes_removed=volumes,networks_removed=networks,private_archives=archives,images_removed=0,current_and_checkpoint_images_retained=True,original_fresh_and_perf_targets_retained=True,global_prune=False,limits=['Only explicitly owned local qualification copy; no existing user data, unknown Docker assets or source deployment removed.','TLS private key remained inside disposable TLS volume; certificate/public transport evidence retained, no system trust changes.'])
with (OUT/'retirement.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],containers=len(after),volumes=len(volumes),networks=2,images_removed=0)))
