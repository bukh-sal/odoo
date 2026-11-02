"""Retire one archived-project empty bridge to free an exhausted default pool."""
import gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;private=ROOT/'.local/g7-performance-10k-01'
project='mp-r0-r1cleand32d742ed8b4';name=project+'_edge';ident='0e4fc75e04e8d89c8ab1f5f37b30fd092cc15b96d3cef7e0669849ee1a55b447'
ownership=ROOT/'.local/g7-docker-retention/ownership.json';owned=json.loads(ownership.read_text());assert owned['projects'][project]
assert project in json.loads((OUT.parent/'20261102-docker-retention-01/audit.json').read_text())['project_counts']
def call(args):return subprocess.check_output(args,timeout=30)
info=json.loads(call(['docker','network','inspect',ident]))[0]
assert info['Name']==name and info['Labels']['com.docker.compose.project']==project and info['Labels']['com.docker.compose.network']=='edge'
assert info['Containers']=={} and info['Driver']=='bridge' and not info['Internal']
assert not call(['docker','ps','--all','--filter','network='+ident,'--format','{{.ID}}']).strip()
archive=private/'retired-empty-network.json.gz';assert not archive.exists()
with gzip.open(archive,'wb') as stream:stream.write(json.dumps(info).encode())
call(['docker','network','rm',ident])
assert ident not in call(['docker','network','ls','--no-trunc','--format','{{.ID}}']).decode().split()
report=dict(result='retired_one_exact_empty_archived_project_network',project=project,name=name,network_id=ident,repository_ownership_sha256=hashlib.sha256(ownership.read_bytes()).hexdigest(),private_topology_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),no_container_or_volume_or_image_removed=True,no_global_prune=True,current_runtime_networks_preserved=True,reason='Default Docker address pools exhausted; known retired project bridge had no endpoint/container users.')
(OUT/'network-retirement.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=report['result'],network=name)))
