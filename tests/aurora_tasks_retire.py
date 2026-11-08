"""Retire exactly the recorded AT-04 disposable sites after qualified/drained work."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import OperatorStore


def docker(*args):return subprocess.check_output(['docker',*args],timeout=90)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('site',choices=['tasks','maintenance','clean']);a=p.parse_args()
    relative='at04-clean49-01' if a.site=='clean' else 'at04-release-01/'+a.site
    local=(ROOT/'.local/aurora-tasks'/relative).resolve();assert local.is_relative_to(ROOT/'.local/aurora-tasks')
    receipt=local/'retired.json';assert not receipt.exists(),'Inspect partial retirement; never overwrite'
    load=lambda p:json.loads(p.read_bytes())
    state=load(local/'state.json');target=load(local/'operator/target.json');project=state['project']
    assert re.fullmatch('mp-r0-r1release[0-9a-f]{12}',project) and target['project']==project
    if a.site=='clean':
        assert load(local/'managed-workload.json')['phase']=='verified'
        drained=load(local/'managed-drain.json')
    else:
        assert load(local/'verify_source-recovery.json')['phase']=='verified'
        drained=load(local/'drain-recovery.json')['profile']
    assert drained['state']=='paused'
    store=OperatorStore(local/'operator/control')
    with store._connect() as db:operations=[r[0] for r in db.execute('SELECT operation_id FROM operations')]
    assert operations and all(store.status(op)['state'] in {'completed','revoked'} for op in operations)
    known={'mp_disposable_r0_r1_release_'+project[-12:]}
    for path in (store.root/'recoveries').glob('*/result.json'):
        record=load(path);assert record['state']=='restored_verified' and record['configuration']['project']==project
        known.update(s['database'] for s in record['configuration']['sites'])
    databases=set(docker('exec',project+'-db-1','psql','-XqAt','-U','postgres','-d','postgres','-c',
        "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname<>'postgres';").decode().splitlines())
    assert databases and databases<=known
    names=[n for n in docker('ps','-a','--format','{{.Names}}').decode().splitlines() if n.startswith(project+'-')]
    assert names
    rows=json.loads(docker('inspect',*names))
    allowed={target['image_id'],
        'sha256:a572f7383c73b5331cc013841db24f371f6d6286e1f353f2c994a554f9162e2a',
        'sha256:d81f7b51697014367236d07ec58b54153fc28f828b72bf247fe5c7487520bcb0',
        'sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f'}
    for row in rows:
        labels=row['Config']['Labels'] or {};assert row['Image'] in allowed
        assert (labels.get('com.modular.disposable')==project or labels.get('com.modular.deployment')==target['deployment_id']
                or labels.get('com.docker.compose.project')==project)
        if labels.get('com.modular.job_pool'):assert not row['State']['Running'] and not row['State'].get('Restarting')
    resources=state['owned_resources']
    for kind,key in [('volume','volumes'),('network','networks')]:
        for row in json.loads(docker(kind,'inspect',*resources[key])):
            assert row['Labels'].get('com.modular.disposable')==project
    record=dict(phase='verified_owned_targets',site=a.site,utc=datetime.now(timezone.utc).isoformat(),project=project,
        containers=[r['Id'] for r in rows],volumes=resources['volumes'],networks=resources['networks'],
        databases=sorted(databases),terminal_operations=len(operations),private_checkpoints_logs_catalog_preserved=True)
    receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    docker('rm','-fv',*record['containers']);docker('volume','rm',*record['volumes']);docker('network','rm',*record['networks'])
    assert not any(n.startswith(project+'-') for n in docker('ps','-a','--format','{{.Names}}').decode().splitlines())
    for kind,key in [('volume','volumes'),('network','networks')]:
        remaining=set(docker(kind,'ls','--format','{{.Name}}').decode().splitlines());assert not remaining.intersection(record[key])
    record['phase']='retired';receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(result='retired',site=a.site,containers=len(rows),volumes=len(record['volumes']),networks=len(record['networks']))))


if __name__=='__main__':main()
