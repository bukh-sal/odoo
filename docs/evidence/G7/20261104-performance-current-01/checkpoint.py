"""Quiesce/checkpoint only the exact retained experimental benchmark."""
import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-performance-current-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'));from modular_platform.operator_os import protect_directory
def load(p):return json.loads(p.read_bytes())
record=load(PRIVATE/'record-before.json');proof=load(OUT/'preflight.json');assert proof['result']=='read_only_retained_benchmark_preflight_passed'
assert record['project']=='mp-g7-perf-6fafdba2c44c' and record['database']=='mp_disposable_r0_r1_g7_perf_6fafdba2c44c'
marker=PRIVATE/'alignment.json';assert not marker.exists();protect_directory(PRIVATE/'logs');protect_directory(PRIVATE/'checkpoints')
state=dict(phase='checking_exact_fixture',project=record['project'],database=record['database'],target_image=proof['new_image'],target_inventory=proof['new_inventory'],created_utc=datetime.now(timezone.utc).isoformat())
def phase(name):state['phase']=name;marker.write_text(json.dumps(state,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(phase=name)),flush=True)
def command(label,args,*,data=None,timeout=120,output_path=None):
 path=output_path or PRIVATE/'logs'/(label+'.stdout')
 with path.open('xb') as stdout,(PRIVATE/'logs'/(label+'.stderr')).open('xb') as stderr:r=subprocess.run(args,input=data,stdout=stdout,stderr=stderr,timeout=timeout)
 assert r.returncode==0,'Inspect exact phase/child/log; never replay fixture mutation'
 return path.read_bytes()
phase('checking_exact_fixture')
rows=json.loads(command('inspect-before-stop',['docker','inspect',record['app_id'],record['edge_id']]))
for row,ident in zip(rows,[record['app_id'],record['edge_id']]):assert row['Id']==ident and row['State']['Running'] and row['Config']['Labels']['com.modular.disposable']==record['project']
assert rows[0]['Image']==record['image_id'] and rows[0]['Config']['Cmd'][-2:]==[record['database'],record['inventory_digest']]
assert all(m['Destination'] not in ['/run/worker-authority','/var/run/docker.sock'] for m in rows[0]['Mounts'])
phase('stopping_only_benchmark_ingress_and_app');command('stop-exact-benchmark',['docker','stop','--time','30',record['edge_id'],record['app_id']])
rows=json.loads(command('inspect-stopped',['docker','inspect',record['app_id'],record['edge_id']]))
assert all(not row['State']['Running'] and row['State']['Status']=='exited' for row in rows)
phase('capturing_existing_benchmark_database')
dump=PRIVATE/'checkpoints/database.dump'
command('database-checkpoint',['docker','exec',record['source_pg_container'],'pg_dump','-U','postgres','--no-owner','-Fc',record['database']],timeout=180,output_path=dump)
assert dump.read_bytes().startswith(b'PGDMP')
command('database-checkpoint-list',['docker','exec','-i',record['source_pg_container'],'pg_restore','--list'],data=dump.read_bytes())
phase('capturing_owned_combined_volume')
script="import pathlib,sys,tarfile;root=pathlib.Path('/checkpoint');assert all(not p.is_symlink() for p in root.rglob('*'));assert (root/'config/odoo_config').is_file() and (root/'data/filestore').is_dir()\nwith tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:archive.add(root,arcname='volume',recursive=True)"
command('private-volume-checkpoint',['docker','run','--rm','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges',
 '--mount','type=volume,source='+record['volume']+',target=/checkpoint,readonly','--entrypoint','/venv/bin/python',record['image_id'],'-c',script],output_path=PRIVATE/'checkpoints/volume.tar.gz')
volume=PRIVATE/'checkpoints/volume.tar.gz';assert volume.read_bytes().startswith(b'\x1f\x8b')
state['checkpoints']={name:dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for name,path in [('database',dump),('private_combined_volume',volume)]}
phase('checkpointed_existing_unmanaged_fixture')
report=dict(result='exact_unmanaged_benchmark_stopped_and_checkpointed',project=record['project'],database=record['database'],checkpoints=state['checkpoints'],stopped_exact_containers=[record['edge_id'],record['app_id']],shared_PostgreSQL_not_stopped=True,new_images_volumes_networks_databases=0,limits=['Private combined-volume checkpoint intentionally includes fixture DB configuration secrets and stays protected; not a public/clean diagnostic.','No native alignment executed yet; this grants no product lifecycle approval.'])
with (OUT/'checkpoint.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],database_bytes=state['checkpoints']['database']['bytes'],volume_bytes=state['checkpoints']['private_combined_volume']['bytes'])))
