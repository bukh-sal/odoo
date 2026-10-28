"""Fixed single-host worker profile, retaining old image workers for recovery."""
import re
import time
from pathlib import Path
from uuid import UUID

from .contracts import load_json
from .deployment import _run
from .operator_os import OperatorError


def wait_ready(worker_id,*,timeout=90):
    deadline=time.monotonic()+timeout
    probe="import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8069/web/login',timeout=5); assert r.status==200"
    while True:
        try:
            _run(['docker','exec',worker_id,'/venv/bin/python','-c',probe])
            return
        except (ValueError,OSError):
            if time.monotonic()>=deadline:raise OperatorError('Guarded registry readiness deadline exceeded')
            time.sleep(1)


def snapshots(configuration):
    raw=_run(['docker','ps','--all','-q','--filter','label=com.docker.compose.project='+configuration['project'],
        '--filter','label=com.docker.compose.service=app']).decode().split()
    if any(not re.fullmatch('[0-9a-f]{12,64}',value) for value in raw):raise OperatorError('Invalid managed worker identity')
    result=[]
    for value in raw:
        item=load_json(_run(['docker','inspect',value]))[0]
        result.append({'container_id':item['Id'],'image_id':item['Image'],'running':item['State']['Running'],
            'name':item['Name'].lstrip('/'),'networks':sorted(item['NetworkSettings']['Networks'])})
    return sorted(result,key=lambda item:item['container_id'])


def ensure(configuration,image_id,operation,*,inventory_digest,suffix='release'):
    if image_id!=configuration['image_id'] or not re.fullmatch('sha256:[0-9a-f]{64}',image_id):raise OperatorError('Immutable worker image required')
    if str(UUID(operation))!=operation or not re.fullmatch('sha256:[0-9a-f]{64}',inventory_digest):raise OperatorError('Exact worker operation/inventory required')
    project=configuration['project'];network=project+'_runtime'
    if suffix not in ('release','restore'):raise OperatorError('Invalid fixed worker purpose')
    previous=snapshots(configuration)
    if any(worker['running'] for worker in previous):raise OperatorError('Old worker must drain before replacement')
    name=project+'-app-'+suffix+'-'+operation.replace('-','')
    arguments=['docker','create','--name',name,'--label','com.docker.compose.project='+project,
            '--label','com.docker.compose.service=app','--label','com.modular.release_operation='+operation,
            '--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256',
            '--memory','1536m','--cpus','2','--tmpfs','/tmp','--network',network,'--network-alias','app',
            '--mount','type=volume,source='+project+'_appconfig,target=/run/secrets,readonly',
            '--mount','type=volume,source='+project+'_filestore,target=/var/lib/modular',
            '--entrypoint','/venv/bin/python',image_id,'-c',Path(__file__).with_name('worker_start.py').read_text(),
            configuration['sites'][0]['database'],inventory_digest]
    worker_id=_run(arguments).decode().strip()
    if not re.fullmatch('[0-9a-f]{64}',worker_id):raise OperatorError('Invalid created worker identity')
    for worker in previous:
        if worker['container_id']!=worker_id and network in worker['networks']:
            if worker['running']:raise OperatorError('Old worker must drain before replacement')
            _run(['docker','network','disconnect',network,worker['container_id']])
    info=load_json(_run(['docker','inspect',worker_id]))[0]
    if network not in info['NetworkSettings']['Networks']:
        _run(['docker','network','connect','--alias','app',network,worker_id])
    return worker_id
