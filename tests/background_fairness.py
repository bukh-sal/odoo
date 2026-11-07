"""Adversarial two-hot-workspace service order across70 ready workspaces."""
import argparse
import json

from background_site import load,write
from background_sustained import native
from background_workers import Probe,wait,docker


SOURCE="""
from datetime import datetime,timedelta,timezone
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
import json
if RESTART:
    from odoo.addons.mp_identity.release import current_release
    release=current_release(env)
    env.cr.execute('DELETE FROM ir_config_parameter WHERE key=%s',['mp.jobs.rotation.'+release['site_id']+'.bulk'])
anchor=datetime.now(timezone.utc).replace(microsecond=0)+timedelta(seconds=30)
jobs={}
for label,row in DATA.items():
    actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][row['user']]['id'],{}),row['public_id'])
    for index in range(30 if label in ('A','B') else 1):
        job=enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs','org.example.background:load',
            dict(iterations=5000000 if RESTART and label in ('A','B') and index==0 else 250000),
            'bx04-fair-'+TAG+'-'+label+'-'+str(index),
            schedule=JobSchedule(anchor,anchor+timedelta(seconds=180),20),version=1)
        jobs[job]=dict(workspace=label,public_id=row['public_id'])
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(jobs=jobs,anchor=anchor.isoformat())))
"""


def main(tag):
    probe=Probe('bx-04-capacity-01');assert not probe.operator._lanes()
    path=probe.site.local/('bx04-fairness-'+tag+'.json');assert not path.exists()
    setup=load(probe.site.local/'bx04-sustained-setup.json')
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    write(path,dict(phase='starting',approval=review['approval']))
    status=probe.operator.run('profile-apply',approval=review['approval']);assert status['state']=='ready'
    restart=tag.startswith('rotation-restart-')
    seed=native(probe,'bx04-fairness-'+tag,SOURCE,DATA=setup['data'],TAG=tag,RESTART=restart)
    assert len(seed['jobs'])==128
    record=dict(phase='seeded',seed=seed,approval=review['approval'],image=probe.target['image_id']);write(path,record)
    ids=','.join("'"+job+"'" for job in seed['jobs'])
    if restart:
        def active():
            rows=json.loads(probe.sql("""SELECT COALESCE(jsonb_agg(jsonb_build_object('job',public_id,
                'generation',claim_generation,'owner',lease_owner)),'[]') FROM mp_job
                WHERE public_id IN ("""+ids+""" ) AND state='running' AND payload->'input'->>'iterations'='5000000'"""))
            for row in rows:
                lane=probe.lane(row['job'],row['generation'])
                if lane:return dict(row,lane=lane)
        victim=wait(active,45)
        before=json.loads(docker('inspect',victim['lane']))[0]
        record.update(phase='crashing_child',victim=victim);write(path,record)
        docker('exec',victim['lane'],'/venv/bin/python','-c',
            "import json,os,signal;p=json.load(open('/tmp/mp-job-health.json'));assert p['state']=='running';os.kill(p['pid'],signal.SIGKILL)")
        stale=native(probe,'bx04-fairness-stale-'+tag,"""
import json,time
from modular_platform import durable
assert env.cr.dbname==EXPECTED_DB
env.cr.commit()
until=time.monotonic()+50
result=None
while time.monotonic()<until:
    with env.registry.cursor() as cr:
        cr.execute('SELECT state,claim_generation FROM mp_job WHERE public_id=%s',[OLD['job']])
        state,generation=cr.fetchone()
        if generation>OLD['generation']:
            old=durable.Claim(OLD['job'],OLD['generation'],OLD['owner'])
            called=[]
            try:durable.run_fenced(cr,old,lambda row:called.append(True) or {'unexpected':True})
            except durable.ClaimLost:pass
            else:raise AssertionError('Interrupted worker escaped generation/owner fence')
            assert not called
            result=dict(stale_apply_denied=True,observed_state=state,generation=generation)
            break
    time.sleep(.1)
assert result is not None,'Interrupted job did not reclaim in the bounded interval'
print('BX04_RESULT='+json.dumps(result))
""",OLD=victim)
        def recovered():
            row=json.loads(docker('inspect',victim['lane']))[0]
            return row if row['RestartCount']>before['RestartCount'] and row['State']['Running'] and row['State'].get('Health',{}).get('Status')=='healthy' else None
        after=wait(recovered,30)
        record.update(phase='restarted',restart=dict(count_before=before['RestartCount'],count_after=after['RestartCount'],stale=stale))
        write(path,record)
    wait(lambda:probe.sql('SELECT count(*) FROM mp_job WHERE public_id IN ('+ids+") AND state='completed'")=='128',120)
    events=[]
    for name in probe.operator._lanes():events.extend(probe.logs(name,lines='2000'))
    claims=[row for row in events if row.get('event')=='claimed' and row.get('job_id') in seed['jobs']]
    assert len({row['job_id'] for row in claims})==128
    assert len(claims)>128 if restart else len(claims)==128
    claims.sort(key=lambda row:row['at'])
    hot=dict(A=0,B=0);peers=set();first_peer=None;hot_at_all_peers=None
    for row in claims:
        origin=seed['jobs'][row['job_id']]
        assert row['workspace']==origin['public_id'] and row['generation']>=1
        label=origin['workspace']
        if label in hot:hot[label]+=1
        else:
            if first_peer is None:first_peer=sum(hot.values())
            peers.add(label)
            if len(peers)==68:hot_at_all_peers=dict(hot)
    assert hot_at_all_peers is not None
    fair=first_peer<=4 and max(hot_at_all_peers.values())<=4
    drain=probe.operator.run('drain');assert drain['state']=='paused' and not probe.operator._lanes()
    record.update(phase='passed' if fair else 'fairness_gap',claims=claims,peers_served=len(peers),
        hot_claims_before_first_peer=first_peer,hot_claims_when_all_peers_started=hot_at_all_peers,
        criterion='First peer within4 hot claims; all68 peers start before either30-job hot backlog consumes more than4 claims.',
        all_jobs_completed_once=True,drain=drain)
    write(path,record)
    print(json.dumps({key:record[key] for key in ('phase','peers_served','hot_claims_before_first_peer','hot_claims_when_all_peers_started')}),flush=True)
    assert fair,'FIFO workspace tie-breaking monopolized service; inspect preserved fair-order evidence'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('tag',choices=['baseline','rotation-01','rotation-restart-01','rotation-02','rotation-restart-02'])
    main(parser.parse_args().tag)
