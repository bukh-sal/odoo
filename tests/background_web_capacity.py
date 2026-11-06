"""Adjust only the independently owned BG fixture's stock Odoo worker sizing."""
import json

from background_site import write
from background_workers import Probe,docker
from modular_platform.workers import wait_ready


COUNTERS="""
rows=open('/proc/net/netstat').read().splitlines()
keys=rows[0].split()
values=rows[1].split()
import json
print(json.dumps({key:int(values[keys.index(key)]) for key in ('ListenOverflows','ListenDrops')}))
"""


def listen(probe):
    return json.loads(docker('exec',probe.target['worker_id'],'/venv/bin/python','-c',COUNTERS))


def main():
    probe=Probe('bg-03-01')
    path=probe.site.local/'bg04-web-capacity.json'
    assert not path.exists()
    before=listen(probe)
    assert before['ListenOverflows']>0 and before['ListenDrops']>0
    worker=probe.target['worker_id']
    edge=probe.project+'-edge-1'
    for name in (worker,edge):
        row,=json.loads(docker('inspect',name))
        assert row['Config']['Labels']['com.docker.compose.project']==probe.project
    settings=json.loads(docker('inspect',worker))[0]['HostConfig']
    assert settings['NanoCpus']==2_000_000_000
    volume=probe.project+'_appconfig'
    row,=json.loads(docker('volume','inspect',volume))
    assert row['Labels']['com.modular.disposable']==probe.project
    result={'phase':'stopping_owned_web','before':before,'web_workers':3,'web_cpus':3,'listen_backlog':24}
    write(path,result)
    docker('stop',edge,worker)
    code="""
from pathlib import Path
import configparser,os,sys
path=Path('/config/odoo_config')
source=path.read_text()
options=configparser.ConfigParser()
options.read_string(source)
assert options['options']['db_name']==sys.argv[1] and options['options'].getint('workers')==2
assert source.count('workers = 2')==1
draft=path.with_name('.bg-workers-staging')
with draft.open('x') as out:out.write(source.replace('workers = 2','workers = 3'))
draft.chmod(0o444)
os.replace(draft,path)
"""
    docker('run','--rm','--network','none','--read-only','--user','0:0','--cap-drop','ALL',
           '--mount','type=volume,source='+volume+',target=/config',
           '--entrypoint','/venv/bin/python',probe.state['image_id'],'-c',code,probe.state['database'])
    docker('update','--cpus','3',worker)
    docker('start',worker)
    wait_ready(worker)
    docker('start',edge)
    result.update(phase='ready',after_restart=listen(probe))
    write(path,result)
    print(json.dumps(result))


if __name__=='__main__':
    main()
