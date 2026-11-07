"""Kill only a managed workspace-slot backend; preserve its work/heartbeat."""
import argparse
import hashlib
import json
import ipaddress
import time

from background_site import load,write
from background_sustained import native
from background_workers import Probe,wait


SOURCE="""
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
import json
row=DATA['A'];actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][row['user']]['id'],{}),row['public_id'])
anchor=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=10)
jobs=[enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:fault',
    dict(mode='heartbeat'),'bx04-slot-'+TAG+'-'+str(index),
    schedule=JobSchedule(anchor,anchor+timedelta(seconds=90),20),version=1) for index in range(2)]
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(jobs=jobs,workspace=row['id'],anchor=anchor.isoformat())))
"""


def main(tag):
    probe=Probe('bx-04-capacity-01');assert not probe.operator._lanes()
    path=probe.site.local/('bx04-slot-loss-'+tag+'.json');assert not path.exists()
    setup=load(probe.site.local/'bx04-sustained-setup.json')
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    write(path,dict(phase='starting',approval=review['approval']))
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    seed=native(probe,'bx04-slot-loss-'+tag,SOURCE,DATA=setup['data'],TAG=tag)
    record=dict(phase='seeded',seed=seed,approval=review['approval'],image=probe.target['image_id']);write(path,record)
    ids=','.join("'"+job+"'" for job in seed['jobs'])
    def sample():
        return json.loads(probe.sql("""SELECT jsonb_build_object('at',extract(epoch FROM clock_timestamp()),
            'running',count(*) FILTER (WHERE state='running'),
            'valid_running',count(*) FILTER (WHERE state='running' AND lease_until>timezone('UTC',clock_timestamp())),
            'completed',count(*) FILTER (WHERE state='completed'),
            'effect_started',count(*) FILTER (WHERE effect_started),
            'details',jsonb_agg(jsonb_build_object('job',public_id,'state',state,'generation',claim_generation,
                'lease_until',lease_until,'progress',progress))) FROM mp_job WHERE public_id IN ("""+ids+")"))
    first=wait(lambda:(value if (value:=sample())['valid_running']==1 else None),30)
    unsigned=int.from_bytes(hashlib.sha256(f"mp-job:{probe.state['site_id']}:bulk:{seed['workspace']}".encode()).digest()[:8],'big')
    upper,lower=unsigned>>32,unsigned&0xffffffff
    sessions=json.loads(probe.sql(f"""SELECT COALESCE(jsonb_agg(jsonb_build_object('pid',l.pid,'client',a.client_addr::text)), '[]')
        FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid
        WHERE l.locktype='advisory' AND l.classid={upper}::oid AND l.objid={lower}::oid AND l.objsubid=1
        AND l.granted AND a.datname=current_database() AND l.pid<>pg_backend_pid()"""))
    assert len(sessions)==1,sessions
    victim=sessions[0]
    lane_ips={network['IPAddress'] for row in probe.operator._lanes().values()
        for network in row['NetworkSettings']['Networks'].values() if row['Config']['Labels']['com.modular.job_pool']=='bulk'}
    assert str(ipaddress.ip_interface(victim['client']).ip) in lane_ips,victim
    record.update(phase='terminating_slot_backend',first=first,backend=victim);write(path,record)
    assert probe.sql('SELECT pg_terminate_backend('+str(victim['pid'])+')')=='t'
    readings=[]
    until=time.monotonic()+40
    while time.monotonic()<until:
        current=sample();readings.append(current)
        if current['completed']==2:break
        time.sleep(.1)
    assert readings[-1]['completed']==2 and all(value['effect_started']==0 for value in readings),readings[-1]
    peak=max(value['valid_running'] for value in readings)
    drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
    record.update(phase='passed' if peak<=1 else 'slot_loss_gap',peak_valid_running=peak,readings=readings,
        no_external_effect=True,all_completed=True,drain=drained)
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],peak_valid_running=peak,all_completed=True)),flush=True)
    assert peak<=1,'Losing the advisory session admitted two simultaneous valid claims in one workspace/pool'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('tag',choices=['baseline','baseline-02','fenced-01'])
    main(parser.parse_args().tag)
