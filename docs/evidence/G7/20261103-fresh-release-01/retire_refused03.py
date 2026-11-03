"""Retire archived realm, including exactly inspected legacy unlabelled seed helper."""
import hashlib,io,json,sys,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from fixture import f,LOCAL,ROOT
state=f.load(LOCAL/'state.json');f.guard(state);project=state['project']
assert project=='mp-g7-qual-291893200389' and state['phase']=='publishing_core_bootstrap'
dump=(LOCAL/'refused-core-only.pg.dump').read_bytes();assert dump==(LOCAL/'logs/refused-project-dump.stdout').read_bytes()
raw=(LOCAL/'refused-core-only-config-filestore.tar').read_bytes();assert raw==(LOCAL/'logs/refused-project-volume-archive02.stdout').read_bytes()
volumes=state['owned_resources']['volumes'];nonpg=[v for v in volumes if not v.endswith('_pgdata')]
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tar:
 assert {m.name.split('/')[0] for m in tar.getmembers()}==set(nonpg) and not any(m.issym() or m.islnk() for m in tar.getmembers())
counts=json.loads((LOCAL/'logs/refused-project-counts.stdout').read_bytes());assert counts==dict(principals=4,workspaces=2,installations=0,jobs=0,outbox=0)
old=json.loads((LOCAL/'logs/refused-project-containers.stdout').read_bytes());assert len(old)==3
rows=json.loads(f.command('refused-project-containers03',['docker','inspect',*[r['Id'] for r in old],project+'-seed-private-volumes']));assert len(rows)==4
expected={project+'-'+x for x in ['db-1','seed-private-volumes','core-init','core-provision']};assert {r['Name'].lstrip('/') for r in rows}==expected
for index,row in enumerate(rows):
 if row['Name'].lstrip('/')==project+'-db-1':
  assert row['Config']['Labels']['com.docker.compose.project']==project and row['State']['Running']
  f.command('refused-project-pg-stop',['docker','stop','--time','20',row['Id']],timeout=40)
 else:
  assert row['State']['Status']=='exited' and row['State']['ExitCode']==0 and row['Image']==state['image_id']
  if row['Name'].lstrip('/')==project+'-seed-private-volumes':assert {m['Name'] for m in row['Mounts']}==set(nonpg)
  else:assert row['Config']['Labels']['com.modular.disposable']==project
 f.command('refused-project-container-retire-'+str(index),['docker','rm',row['Id']])
for index,name in enumerate(volumes):
 assert not f.command('refused-volume-unmounted-'+str(index),['docker','ps','-aq','--filter','volume='+name]).strip()
 f.command('refused-volume-retire-'+str(index),['docker','volume','rm',name])
for index,name in enumerate(state['owned_resources']['networks']):
 network=json.loads(f.command('refused-network-inspect-'+str(index),['docker','network','inspect',name]))[0]
 assert network['Labels']['com.modular.disposable']==project and not network['Containers']
 f.command('refused-network-retire-'+str(index),['docker','network','rm',name])
protected=f.load(LOCAL/'original-preservation-query.json')
actual=json.loads(f.command('refused-original-preserved',['docker','exec','-i',protected['project']+'-db-1','psql','-X','-qAt','-U','postgres','-d',protected['database'],'-v','ON_ERROR_STOP=1'],input=protected['query'].encode()));assert actual==protected['expected'];f.guard(state)
f.save('refused-project-retirement.json',dict(result='archived_and_retired_exact_core_only_project_after_name_guard_refusal',project=project,counts=counts,containers=4,volumes=6,networks=2,images_removed=0,database_dump_sha256=hashlib.sha256(dump).hexdigest(),config_filestore_tar_sha256=hashlib.sha256(raw).hexdigest(),dump_toc_checked=True,archive_checked=True,original17table_hashes_configs_exact=True,reason='mp-g7-qual naming is outside existing mp-r0-r1[a-z0-9]+ adapter profile; no guard weakening or product image change',next='Replacement project name is validated with actual DockerObserver before files/Docker allocation; use existing qualified fixture path.'))
f.phase(state,'archived_refused_project_retired');print('Exact refused core-only project archived/retired; original17tables/configs unchanged; no images removed',flush=True)
