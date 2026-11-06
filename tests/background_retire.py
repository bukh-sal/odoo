"""Retire only the explicitly inventoried disposable BG Docker objects."""
import json
import re
import sqlite3
import subprocess
import sys

from background_site import ROOT,load,write
from background_workers import docker


LOCAL=ROOT/'.local/background-qualification'
BUILDS=('bg-02-reference-build-01','bg-03-managed-build-01','bg-03-managed-build-02',
        'bg-03-managed-build-03','bg-03-successor-build-01','bg-03-successor-build-02')


def rows(*args):
    return json.loads(docker(*args))


def retire_site(run):
    directory=LOCAL/run
    site=load(directory/'state.json')
    project=site['project']
    assert re.fullmatch(r'mp-r0-r1release[a-f0-9]{12}',project)
    names=docker('ps','-a','--format','{{.Names}}').decode().splitlines()
    containers=[name for name in names if name.startswith(project+'-')]
    if containers:
        for row in rows('inspect',*containers):
            labels=row['Config']['Labels']
            assert (labels.get('com.docker.compose.project')==project
                    or labels.get('com.modular.disposable')==project
                    or labels.get('com.modular.deployment')==site['deployment_id'])
    volumes,networks=[site['owned_resources'][key] for key in ('volumes','networks')]
    for kind,values in (('volume',volumes),('network',networks)):
        for row in rows(kind,'inspect',*values):
            assert row['Labels'].get('com.modular.disposable')==project
    if containers:docker('rm','-fv',*containers)
    docker('volume','rm',*volumes)
    docker('network','rm',*networks)
    assert not any(name.startswith(project+'-') for name in docker('ps','-a','--format','{{.Names}}').decode().splitlines())
    return dict(containers=len(containers),volumes=len(volumes),networks=len(networks))


def early():
    assert load(LOCAL/'bg-02-01/state.json')['phase']=='bg02_probed'
    assert load(LOCAL/'bg-03-01/state.json')['phase']=='background_installed'
    receipt=LOCAL/'early-retired.json'
    assert not receipt.exists()
    record={'bg02_site':retire_site('bg-02-01')}
    for kind,name in [('container','mp-bg-qual-pg'),('network','mp-bg-qual-net')]:
        row,=rows(kind,'inspect',name)
        labels=row['Config']['Labels'] if kind=='container' else row['Labels']
        assert labels.get('mp.bg.owner')=='bg-01-04'
        docker(kind,'rm',*(['-fv'] if kind=='container' else []),name)
    record['primitive_tmpfs_target']=dict(containers=1,volumes=0,networks=1)
    write(receipt,record)
    print(json.dumps(record),flush=True)


def final():
    assert any(path.exists() and load(path)['phase']=='passed' for path in
               [LOCAL/'bg-03-01'/name for name in ('bg04-load.json','bg04-load-tuned.json','bg04-load-scaled.json',
                                                    'bg04-load-aligned.json','bg04-load-aligned-02.json',
                                                    'bg04-load-linux-peer.json','bg04-load-web-three.json',
                                                    'bg04-load-db-four.json','bg04-load-one-urgent.json')])
    receipt=LOCAL/'final-retired.json'
    assert not receipt.exists()
    operations=set()
    for run in ('bg-02-01','bg-03-01'):
        db=LOCAL/run/'operator/control/control.sqlite3'
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as con:
            operations.update(row[0] for row in con.execute('SELECT operation_id FROM operations'))
    known={'modular-platform:retained-'+operation for operation in operations}
    candidates={}
    for build in BUILDS:
        path=ROOT/'docs/evidence/G7'/build/'candidate-build.json'
        if not path.exists():
            path=ROOT/'.local/operator/builds'/(build+'.json')
        row=load(path)
        candidates[row['image_id']]=row['tag']
        known.add(row['tag'])
    result={**load(LOCAL/'early-retired.json'),'bg03_site':retire_site('bg-03-01'),'images':[]}
    for image in candidates:
        assert not docker('ps','-aq','--filter','ancestor='+image).strip()
        row,=rows('image','inspect',image)
        tags=set(row['RepoTags'])
        assert tags and tags<=known
        docker('image','rm',*sorted(tags))
        result['images'].extend(sorted(tags))
    write(receipt,result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    (early if sys.argv[1]=='early' else final)()
