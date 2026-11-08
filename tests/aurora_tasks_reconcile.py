"""Rollback-isolated native carry-forward classification, not operator release proof."""
import json
from datetime import timedelta
from uuid import uuid4
from odoo import api,fields
from odoo.addons.mp_core import job_dispatch,native_jobs
from odoo.addons.mp_identity.release import current_release
from odoo.exceptions import AccessError

checks=[]
with env.registry.cursor() as cr:
    actor=api.Environment(cr,FIXTURE['users']['alice']['id'],{},su=False)
    release=current_release(actor)
    listing=actor['mp.aurora.task.list'].create(dict(name='Carry-forward classification'))
    task=actor['mp.aurora.task'].create(dict(name='Pending native occurrence',list_id=listing.id,
        assignee_id=actor.uid,due_date=fields.Datetime.now()+timedelta(hours=1),reminder='0'))
    cr.execute('SELECT job_id FROM mp_aurora_reminder WHERE task_id=%s',[task.id]);ident=cr.fetchone()[0]
    task.flush_recordset()
    cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident]);before=cr.fetchone()[0]
    definition=job_dispatch.DEFINITIONS[(before['handler'],before['handler_version'])]
    if EXPECT_FIXED:
        try:
            with cr.savepoint():native_jobs.authorized(api.Environment(cr,1,{}),before,definition,previous_release=release['release_digest'])
        except AccessError:pass
        else:raise AssertionError('Enabled control admitted old-release classification')
        checks.append('old-release authority classification denied while dispatch enabled')
    # Trusted, rollback-only fixture setup; no operator approval/resume claim.
    cr.execute("UPDATE mp_dispatch_control SET state='paused' WHERE site_id=%s",[release['site_id']])
    cr.execute("UPDATE mp_job SET state='held' WHERE state IN ('pending','retry','running')")
    result=job_dispatch.reconcile_release(api.Environment(cr,1,{}),previous_release=release['release_digest'],target_release=release['release_digest'])
    decision=next(r for r in result['jobs'] if r['job_id']==ident)
    assert decision['decision']==('resumable' if EXPECT_FIXED else 'held'),decision
    cr.execute('SELECT to_jsonb(j) FROM mp_job j WHERE public_id=%s',[ident]);after=cr.fetchone()[0]
    if EXPECT_FIXED:
        for key in ['workspace_id','actor_id','installation_id','input_digest','payload','available_at','deadline_at','idempotency_key']:
            assert after[key]==before[key],key
        assert after['claim_generation']==before['claim_generation']+1 and after['state']=='pending'
        assert after['workspace_id'] is None and 'binding' not in after['payload']['context']
        checks.append('native occurrence resumable with exact actor/input/identity/timing and no fabricated binding')
        cr.execute('SELECT state FROM mp_dispatch_control WHERE site_id=%s',[release['site_id']]);assert cr.fetchone()==('paused',)
        checks.append('classification preserves closed dispatch and requires independent resume')
    cr.rollback()
print('MP_AT_RECONCILE='+json.dumps(dict(result='passed' if EXPECT_FIXED else 'counterexample_confirmed',
    decision=decision,checks=checks,transaction_rolled_back=True,scope='native classifier only; final independent lifecycle remains pending'),sort_keys=True))
