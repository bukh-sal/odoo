"""Same-release runtime samples for the controlled BX-04 burst comparison."""
import json

from background_site import load,write
from background_sustained import native
from background_workers import Probe,wait


SOURCE="""
from datetime import datetime,timedelta,timezone
import json
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.job_dispatch import enqueue_scheduled
from modular_platform.durable import JobSchedule
jobs=[]
for index in range(40):
    label=sorted(DATA)[index%70];row=DATA[label]
    actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][row['user']]['id'],{}),row['public_id'])
    report=index<20;handler='org.example.background:'+('report' if report else 'load')
    values=dict(first=row['first'],last=row['last']) if report else dict(iterations=[250000,1000000,5000000][index%3])
    now=datetime.now(timezone.utc)
    jobs.append(enqueue_scheduled(actor['mp.background.task']._job_env(),'jobs',handler,values,
        'bx04-calibration-'+str(index),schedule=JobSchedule(now,now+timedelta(seconds=180),20),version=2 if report else 1))
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(jobs=jobs)))
"""


def main():
    probe=Probe('bx-04-capacity-01');assert not probe.operator._lanes()
    path=probe.site.local/'bx04-calibration.json';assert not path.exists()
    setup=load(probe.site.local/'bx04-sustained-setup.json')
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    write(path,dict(phase='starting',approval=review['approval']))
    result=probe.operator.run('profile-apply',approval=review['approval']);assert result['state']=='ready'
    seed=native(probe,'bx04-calibration',SOURCE,DATA=setup['data'])
    record=dict(phase='seeded',seed=seed,approval=review['approval']);write(path,record)
    wait(lambda:all(probe.row(job)['state']=='completed' for job in seed['jobs']),100)
    snapshot=probe.operator.run('capacity');assert len(snapshot['samples'])==40
    assert snapshot['complete'] and snapshot['fleet_state']=='ready'
    assert sum(row['handler_version']=='org.example.background:report:2' for row in snapshot['samples'])==20
    record.update(phase='passed',snapshot=snapshot,drain=probe.operator.run('drain'))
    assert record['drain']['state']=='paused' and not probe.operator._lanes()
    write(path,record);print(json.dumps(dict(phase='passed',samples=40)),flush=True)


if __name__=='__main__':main()
