"""Native authority, concurrent starts and post-successor apply rollback."""
from background_chunks import BASIC
from background_site import load,write
from background_sustained import native
from background_workers import Probe


SOURCE="""
from concurrent.futures import ThreadPoolExecutor
import time
from odoo.service.model import retrying
from modular_platform.durable import RetryJob
model=actor('alice','A');other=actor('bob','B');viewer=actor('alice','B')
first,last=FINAL['big_first'],FINAL['big_last']
main=FINAL['run'];source=model._report_row(main)
def counts():
    env.cr.execute('SELECT (SELECT count(*) FROM mp_background_report),(SELECT count(*) FROM mp_job)');return env.cr.fetchone()
baseline=counts()
try:
    with env.cr.savepoint():
        model._start_report(source['request_first'],source['request_last'],'bx05-final-outer-rollback')
        raise ValidationError('Deliberate outer rollback')
except ValidationError:pass
assert counts()==baseline
original_queue=type(model)._queue_report_chunk
def enqueue_failure(self,row,cursor):
    original_queue(self,row,cursor)
    raise ValidationError('Deliberate caught post-enqueue failure')
with patch.object(type(model),'_queue_report_chunk',enqueue_failure):
    try:model._start_report(source['request_first'],source['request_last'],'bx05-final-enqueue-rollback')
    except ValidationError:pass
    else:raise AssertionError('Failure missing')
model.create(dict(name='BX05 unrelated commit',points=1));env.cr.commit()
assert counts()==baseline and model.search_count([('name','=','BX05 unrelated commit')])==1
foreign=other.search([('name','like','BX05 foreign %')],order='id')
owned_b=viewer._start_report(foreign[0].id,foreign[-1].id,'bx05-viewer-owned')
try:other._report_status(owned_b)
except (AccessError,MissingError,PublicError):pass
else:raise AssertionError('Different actor in same workspace read the run')
assert viewer._cancel_report(owned_b)
unknown=viewer._start_report(foreign[0].id,foreign[-1].id,'bx05-unknown-contract')
unknown_row=viewer._report_row(unknown)
env['mp.background.report'].sudo().browse(unknown_row['id']).write(dict(contract_version=99));env.cr.commit()
outcome=run_once(env.registry,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['B']['id'])
assert outcome['state']=='dead_letter' and outcome['error_code']=='CONFLICT',outcome
env.cr.rollback();env.invalidate_all();viewer=actor('alice','B')
assert viewer._report_row(unknown)['cursor']==0
assert viewer._cancel_report(unknown);env.cr.commit()
revoked=viewer._start_report(foreign[0].id,foreign[-1].id,'bx05-revoked-origin');env.cr.commit()
env.cr.execute("UPDATE mp_membership SET state='revoked' WHERE workspace_id=%s AND principal_id=(SELECT id FROM mp_principal WHERE public_id=%s)",
    [FIXTURE['workspaces']['B']['id'],FIXTURE['users']['alice']['principal_id']]);env.cr.commit()
try:viewer._report_status(revoked)
except (AccessError,MissingError,PublicError):pass
else:raise AssertionError('Revoked actor read run metadata')
outcome=run_once(env.registry,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['B']['id'])
assert outcome['state']=='dead_letter' and outcome['error_code']=='FORBIDDEN',outcome
env.cr.rollback();env.invalidate_all()
env.cr.execute("UPDATE mp_membership SET state='active' WHERE workspace_id=%s AND principal_id=(SELECT id FROM mp_principal WHERE public_id=%s)",
    [FIXTURE['workspaces']['B']['id'],FIXTURE['users']['alice']['principal_id']]);env.cr.commit()
viewer=actor('alice','B');assert viewer._report_row(revoked)['cursor']==0
assert viewer._cancel_report(revoked);env.cr.commit()
def submit(index):
    with env.registry.cursor() as cr:
        metadata=api.Environment(cr,1,{})
        def request():
            current=scoped_environment(api.Environment(cr,FIXTURE['users']['alice']['id'],{}),FIXTURE['workspaces']['A']['public_id'])['mp.background.task']
            return current._start_report(first,last,'bx05-concurrent')
        return retrying(request,metadata)
with ThreadPoolExecutor(max_workers=4) as pool:runs=list(pool.map(submit,range(4)))
assert len(set(runs))==1
env.cr.rollback();env.invalidate_all();model=actor('alice','A')
ident=runs[0];before=model._report_row(ident)
assert before['total']==5000 and before['cursor']==0
env.cr.execute("SELECT count(*) FROM mp_job WHERE handler='org.example.background:report_chunk' AND payload->'input'->>'run'=%s",[ident])
assert env.cr.fetchone()==(1,);env.cr.commit()
observed=[];original_apply=type(model)._apply_report_chunk
def fail_apply(self,values,prepared,computed):
    result=original_apply(self,values,prepared,computed)
    row=self._report_row(ident)
    assert row['cursor']==100 and row['points']==4950
    self.env.cr.execute('SELECT state FROM mp_job WHERE public_id=%s',[row['job_public_id']]);assert self.env.cr.fetchone()==('pending',)
    observed.append(dict(cursor=100,successor_visible_inside_transaction=True))
    raise RetryJob()
with patch.object(type(model),'_apply_report_chunk',fail_apply):
    outcome=run_once(env.registry,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['A']['id'])
assert outcome['state']=='retry' and observed==[dict(cursor=100,successor_visible_inside_transaction=True)],outcome
env.cr.rollback();env.invalidate_all();model=actor('alice','A');after=model._report_row(ident)
assert after==before
env.cr.execute("SELECT count(*) FROM mp_job WHERE payload->'input'->>'run'=%s",[ident]);assert env.cr.fetchone()==(1,)
env.cr.execute('SELECT count(*) FROM mp_job_identity WHERE idempotency_key=%s',[ident+':chunk:100']);assert env.cr.fetchone()==(0,)
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(run=ident,big_first=first,big_last=last,total=5000,points=2497500,
    current_job=after['job_public_id'],initial_rollback=True,caught_enqueue_rollback=True,unrelated_commit=True,
    same_workspace_actor_denied=True,unknown_contract_denied=True,revoked_origin_denied=True,
    concurrent_requests=4,unique_runs=1,unique_initial_jobs=1,apply_fault=observed,
    cursor_and_successor_rolled_back=True,retry_state=outcome['state'])))
"""


def main():
    probe=Probe('bx-05-chunks-01');path=probe.site.local/'bx05-atomicity.json'
    assert not path.exists() and not probe.operator._lanes()
    final=load(probe.site.local/'bx05-basic-final.json');assert final['phase']=='passed'
    prefix=BASIC.split("model=actor('alice','A');other=actor('bob','B')",1)[0]
    write(path,dict(phase='running',image=probe.state['image_id']))
    result=native(probe,'bx05-atomicity',prefix+SOURCE,FINAL=final['result'])
    write(path,dict(phase='passed',image=probe.state['image_id'],result=result))
    print(dict(phase='passed',concurrent=4,run=result['run'],retry_pending=True),flush=True)


if __name__=='__main__':main()
