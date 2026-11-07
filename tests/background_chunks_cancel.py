"""Native cancellation while compute is stopped, plus deleted-source fencing."""
import json
import time

from background_chunks import BASIC
from background_site import load,write
from background_sustained import native
from background_workers import Probe,docker,wait


START="""
model=actor('alice','A')
ident=model._start_report(FIRST,LAST,'bx05-partial-cancel');env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(run=ident)))
"""
CANCEL="""
from odoo.service.model import retrying
def cancel():
    model=actor('alice','A');before=model._report_row(RUN)
    assert before['cursor']==CURSOR and before['state']=='running'
    assert model._cancel_report(RUN)
    after=model._report_row(RUN)
    assert after['cursor']==CURSOR and after['points']==before['points']
    assert after['state']=='cancelled' and after['snapshot'] is None
    return dict(cursor=after['cursor'],points=after['points'],snapshot_cleared=True)
result=retrying(cancel,env)
print('BX04_RESULT='+json.dumps(result))
"""
DELETION="""
model=actor('alice','A');tasks=model.create([dict(name='BX05 deleted-source '+str(n),points=5) for n in range(3)])
ident=model._start_report(tasks[0].id,tasks[-1].id,'bx05-deleted-source');env.cr.commit()
env.cr.execute('DELETE FROM mp_background_task WHERE id=%s AND workspace_id=%s AND name=%s',
    [tasks[1].id,FIXTURE['workspaces']['A']['id'],'BX05 deleted-source 1']);assert env.cr.rowcount==1
env.cr.commit()
result=run_once(env.registry,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['A']['id'])
assert result['state']=='dead_letter' and result['error_code']=='FORBIDDEN',result
env.cr.rollback();env.invalidate_all();model=actor('alice','A')
state=model._report_status(ident);assert state['state']=='blocked' and state['cursor']==0 and state['points']==0
assert model._cancel_report(ident);env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(deleted_source_denied=True,cursor_unchanged=True,explicit_cleanup=True)))
"""


def main():
    probe=Probe('bx-05-chunks-01');path=probe.site.local/'bx05-cancel.json'
    assert not path.exists() and not probe.operator._lanes()
    source=load(probe.site.local/'bx05-atomicity.json')['result']
    prefix=BASIC.split("model=actor('alice','A');other=actor('bob','B')",1)[0]
    record=dict(phase='starting',image=probe.state['image_id']);write(path,record)
    review=probe.operator.run('profile-review',urgent_lanes=1,bulk_lanes=2)
    assert probe.operator.run('profile-apply',approval=review['approval'])['state']=='ready'
    seed=native(probe,'bx05-cancel-seed',prefix+START,FIRST=source['big_first'],LAST=source['big_last'])
    ident=seed['run'];record.update(phase='running',run=ident,approval=review['approval']);write(path,record)
    query="""SELECT jsonb_build_object('cursor',r.cursor,'points',r.points,'state',r.state,
        'job',j.public_id,'job_state',j.state,'generation',j.claim_generation)
        FROM mp_background_report r JOIN mp_job j ON j.public_id=r.job_public_id WHERE r.public_id='"""+ident+"'"
    def observed():return json.loads(probe.sql(query))
    def active():
        row=observed()
        return row if 100<=row['cursor']<4500 and row['job_state']=='running' else None
    frozen=None
    for _ in range(3):
        row=wait(active,25);lane=probe.lane(row['job'],row['generation']);assert lane
        item,=json.loads(docker('inspect',lane))
        assert item['Image']==probe.state['image_id'] and item['Config']['Labels']['com.modular.job_site']==probe.state['site_id']
        pid=int(docker('exec',lane,'/venv/bin/python','-c',
            "import json,os,signal;p=json.load(open('/tmp/mp-job-health.json'));assert p['pool']=='bulk';print(p['pid'],flush=True);os.kill(p['pid'],signal.SIGSTOP)").decode().strip())
        after=observed()
        if after['job_state']=='running' and probe.lane(after['job'],after['generation'])==lane:
            frozen=dict(**after,lane=lane,pid=pid);break
        docker('exec',lane,'/venv/bin/python','-c','import os,signal;os.kill('+str(pid)+',signal.SIGCONT)')
    assert frozen is not None
    record.update(phase='compute_stopped',frozen=frozen);write(path,record)
    try:
        cancelled=native(probe,'bx05-cancel-active',prefix+CANCEL,RUN=ident,CURSOR=frozen['cursor'])
        record.update(phase='cancelled',cancel=cancelled);write(path,record)
    finally:
        docker('exec',frozen['lane'],'/venv/bin/python','-c','import os,signal;os.kill('+str(frozen['pid'])+',signal.SIGCONT)')
    time.sleep(4)
    after=observed();assert after['cursor']==frozen['cursor'] and after['state']=='cancelled' and after['job_state']=='cancelled'
    assert after['points']==sum(n%1000 for n in range(after['cursor']))
    rows=json.loads(probe.sql("""SELECT jsonb_build_object('completed_rows',COALESCE(sum((result->>'count')::int),0),
        'successors',count(*) FILTER (WHERE (payload->'input'->>'cursor')::int>"""+str(after['cursor'])+"""))
        FROM mp_job WHERE payload->'input'->>'run'='"""+ident+"'"))
    assert rows==dict(completed_rows=after['cursor'],successors=0),rows
    drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
    record.update(phase='partial_cancel_passed',after=after,rows=rows,drain=drained);write(path,record)
    deletion=native(probe,'bx05-deleted-source',prefix+DELETION)
    record.update(phase='passed',deletion=deletion);write(path,record)
    print(dict(phase='passed',committed_rows=after['cursor'],obsolete_apply_did_not_advance=True,deleted_source_denied=True),flush=True)


if __name__=='__main__':main()
