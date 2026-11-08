"""Retire exactly one recorded disposable AR Reference realm, including restores."""
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


def docker(*args):
    return subprocess.check_output(['docker',*args],timeout=90)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('realm',choices=['baseline46','aurora46','fault46','consumer47']);a=p.parse_args()
    local=(ROOT/'.local/addon-cleanup'/a.realm/'private/reference').resolve()
    assert local.is_relative_to(ROOT/'.local/addon-cleanup')
    receipt=local/'ar-retirement.json';assert not receipt.exists(),'Inspect partial retirement before continuing'
    state=json.loads((local/'state.json').read_bytes());target=json.loads((local/'operator/target.json').read_bytes())
    project=state['project'];assert re.fullmatch('mp-r0-r1release[a-f0-9]{12}',project) and target['project']==project
    store=OperatorStore(local/'operator/control')
    with store._connect() as db:
        operations=[r[0] for r in db.execute('SELECT operation_id FROM operations')]
    statuses=[store.status(op) for op in operations]
    assert all(s['state'] in ('completed','revoked') for s in statuses),'An operation is not terminal/reconciled'
    known={'mp_disposable_r0_r1_release_'+project[-12:]}
    for file in (store.root/'recoveries').glob('*/result.json'):
        recovery=json.loads(file.read_bytes());configuration=recovery['configuration']
        assert configuration['project']==project and recovery['state']=='restored_verified'
        known.update(site['database'] for site in configuration['sites'])
    assert len(target['sites'])==1 and target['sites'][0]['database'] in known
    databases=set(docker('exec',project+'-db-1','psql','-XqAt','-U','postgres','-d','postgres','-c',
        "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname<>'postgres';").decode().splitlines())
    assert databases and databases<=known,'Unexpected databases require review; no resources removed'
    names=docker('ps','-a','--format','{{.Names}}').decode().splitlines()
    selected=[n for n in names if n.startswith(project+'-')]
    rows=json.loads(docker('inspect',*selected)) if selected else []
    for row in rows:
        labels=row['Config']['Labels'] or {}
        assert (labels.get('com.modular.disposable')==project or labels.get('com.modular.deployment')==target['deployment_id']
                or labels.get('com.docker.compose.project')==project)
        if labels.get('com.modular.job_pool'):
            assert not row['State']['Running'] and not row['State'].get('Restarting'),'Drain reviewed job lanes first'
    resources=state['owned_resources']
    for kind,key in [('volume','volumes'),('network','networks')]:
        for row in json.loads(docker(kind,'inspect',*resources[key])):
            assert row['Labels'].get('com.modular.disposable')==project
    record=dict(phase='verified_exact_owned_resources',utc=datetime.now(timezone.utc).isoformat(),realm=a.realm,
        project=project,containers=[r['Id'] for r in rows],volumes=resources['volumes'],networks=resources['networks'],
        databases=sorted(databases),terminal_operations=len(statuses),private_checkpoints_exports_logs_preserved=True)
    receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='\n')
    if rows:docker('rm','-fv',*record['containers'])
    docker('volume','rm',*record['volumes']);docker('network','rm',*record['networks'])
    assert not any(n.startswith(project+'-') for n in docker('ps','-a','--format','{{.Names}}').decode().splitlines())
    record['phase']='retired';receipt.write_text(json.dumps(record,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(result='retired_exact_owned_reference',realm=a.realm,containers=len(rows),volumes=len(record['volumes']),networks=len(record['networks']))))


if __name__=='__main__':main()
