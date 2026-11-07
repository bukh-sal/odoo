"""BX-05 approved reference upgrade and real native continuation checks."""
import argparse
import hashlib
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

from background_site import Catalog,configuration,load,write,ROOT
from background_sustained import native
from background_workers import Probe
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.release_staging import StageStore,prepare_staged_plan
from reference_package import assemble


BASIC="""
import json
from uuid import uuid4
from unittest.mock import patch
from odoo import api
from odoo.exceptions import AccessError,MissingError,ValidationError
from odoo.addons.mp_identity.scopes import scoped_environment
from odoo.addons.mp_core.controllers import PublicError
from modular_platform.job_runner import run_once
from odoo.addons.mp_core import job_dispatch
from modular_platform.durable import JobSchedule
from datetime import datetime,timedelta,timezone
assert env.cr.dbname==EXPECTED_DB
def actor(who,workspace):
    return scoped_environment(api.Environment(env.cr,FIXTURE['users'][who]['id'],{}),FIXTURE['workspaces'][workspace]['public_id'])['mp.background.task']
model=actor('alice','A');other=actor('bob','B')
tasks=model.create([dict(name='BX05 snapshot '+str(n),points=n%1000) for n in range(1201)])
foreign_rows=other.create([dict(name='BX05 foreign '+str(n),points=999) for n in range(20)])
first,last=tasks[0].id,tasks[-1].id;assert last-first==1200
env.cr.commit()
print('BX05_CHECKPOINT='+json.dumps(dict(phase='source_created',first=first,last=last)),flush=True)
def counts():
    env.cr.execute('SELECT (SELECT count(*) FROM mp_background_report),(SELECT count(*) FROM mp_job)');return env.cr.fetchone()
baseline=counts()
try:
    with env.cr.savepoint():
        model._start_report(first,last,'bx05-outer-rollback')
        raise ValidationError('Deliberate outer rollback')
except ValidationError:pass
assert counts()==baseline
original=type(model)._queue_report_chunk
def lost(self,row,cursor):
    original(self,row,cursor)
    raise ValidationError('Deliberate failure after first enqueue')
with patch.object(type(model),'_queue_report_chunk',lost):
    try:model._start_report(first,last,'bx05-enqueue-rollback')
    except ValidationError:pass
    else:raise AssertionError('Expected enqueue failure')
env.cr.commit();assert counts()==baseline
ident=model._start_report(first,last,'bx05-snapshot')
assert model._start_report(first,last,'bx05-snapshot')==ident
try:model._start_report(first,last-1,'bx05-snapshot')
except PublicError as error:assert error.code=='CONFLICT'
else:raise AssertionError('Changed request accepted')
env.cr.commit()
assert counts()==(1,1)
print('BX05_CHECKPOINT='+json.dumps(dict(phase='queued',run=ident)),flush=True)
denials=0
for foreign in (other,actor('alice','B')):
    try:foreign._report_status(ident)
    except (AccessError,MissingError,PublicError):denials+=1
    else:raise AssertionError('Foreign run exposed')
try:model.env['mp.background.report'].search([])
except AccessError:denials+=1
else:raise AssertionError('Private metadata exposed through ORM')
try:
    with env.cr.savepoint():
        now=datetime.now(timezone.utc)
        job_dispatch.enqueue_scheduled(other._job_env(),'jobs','org.example.background:report_chunk',dict(run=ident,cursor=0),
            'bx05-foreign',version=1,schedule=JobSchedule(now,now+timedelta(minutes=5),20))
except (AccessError,MissingError,PublicError):denials+=1
else:raise AssertionError('Foreign run enqueued')
assert denials==4
tasks.write(dict(points=0));env.cr.commit()
committed=[]
for index in range(13):
    result=run_once(env.registry,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['A']['id'])
    assert result['state']=='completed',result
    env.cr.rollback();env.invalidate_all()
    state=model._report_status(ident);committed.append(state)
    assert state['cursor']==min((index+1)*100,1201)
    assert state['points']==sum(n%1000 for n in range(state['cursor']))
    if index<12:assert state['state']=='running' and state['job_state']=='pending'
    else:assert state['state']=='completed'
    env.cr.commit()
    print('BX05_CHECKPOINT='+json.dumps(dict(phase='chunk_committed',cursor=state['cursor'])),flush=True)
assert state['cursor']==state['total']==1201 and state['points']==519600
assert model._report_row(ident)['snapshot'] is None
assert model._start_report(first,last,'bx05-snapshot')==ident
assert not model._cancel_report(ident)
env.cr.execute("SELECT count(*),count(DISTINCT payload->'input'->>'cursor'),sum((result->>'count')::int) FROM mp_job WHERE handler='org.example.background:report_chunk'")
assert env.cr.fetchone()==(13,13,1201)
boundary=model._start_report(first,foreign_rows[-1].id,'bx05-scope-boundary')
boundary_row=model._report_row(boundary)
assert boundary_row['total']==1201 and all(item[0]<=last for item in boundary_row['snapshot'])
assert model._cancel_report(boundary)
assert model._report_row(boundary)['snapshot'] is None
big=model.create([dict(name='BX05 heavy '+str(n),points=n%1000) for n in range(5001)])
env.cr.commit();before=counts()
try:model._start_report(big[0].id,big[-1].id,'bx05-too-large')
except ValidationError:pass
else:raise AssertionError('Oversized snapshot accepted')
assert counts()==before
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(run=ident,first=first,last=last,scope_denials=denials,
    outer_rollback=True,caught_enqueue_rollback=True,duplicate_stable=True,committed=committed,
    chunks=13,count=1201,points=519600,snapshot_preserved_after_source_edit=True,terminal_snapshot_cleared=True,
    range_excluded_foreign_rows=True,oversize_refused=True,big_first=big[0].id,big_last=big[-2].id)))
"""


RESUME="""
model=actor('alice','A');other=actor('bob','B')
env.cr.execute("SELECT public_id FROM mp_background_report WHERE request_key='bx05-snapshot'")
ident,=env.cr.fetchone();row=model._report_row(ident)
assert row['cursor']==0 and row['total']==1201 and row['state']=='running'
first,last=row['request_first'],row['request_last']
foreign_rows=other.search([('name','like','BX05 foreign %')],order='id');assert len(foreign_rows)==20
def counts():
    env.cr.execute('SELECT (SELECT count(*) FROM mp_background_report),(SELECT count(*) FROM mp_job)');return env.cr.fetchone()
baseline=counts()
try:
    with env.cr.savepoint():
        model._start_report(first,last,'bx05-outer-rollback-02')
        raise ValidationError('Deliberate rollback')
except ValidationError:pass
assert counts()==baseline
original=type(model)._queue_report_chunk
def lost(self,row,cursor):
    original(self,row,cursor)
    raise ValidationError('Deliberate post-enqueue failure')
with patch.object(type(model),'_queue_report_chunk',lost):
    try:model._start_report(first,last,'bx05-enqueue-rollback-02')
    except ValidationError:pass
    else:raise AssertionError('Expected failure')
env.cr.commit();assert counts()==baseline
assert model._start_report(first,last,'bx05-snapshot')==ident
try:model._start_report(first,last-1,'bx05-snapshot')
except PublicError as error:assert error.code=='CONFLICT'
else:raise AssertionError('Changed range accepted')
denials=0
for foreign in (other,actor('alice','B')):
    try:foreign._report_status(ident)
    except (AccessError,MissingError,PublicError):denials+=1
    else:raise AssertionError('Foreign outcome exposed')
try:model.env['mp.background.report'].search([])
except AccessError:denials+=1
else:raise AssertionError('Private metadata exposed')
try:
    with env.cr.savepoint():
        now=datetime.now(timezone.utc)
        job_dispatch.enqueue_scheduled(other._job_env(),'jobs','org.example.background:report_chunk',dict(run=ident,cursor=0),
            'bx05-foreign-02',version=1,schedule=JobSchedule(now,now+timedelta(minutes=5),20))
except (AccessError,MissingError,PublicError):denials+=1
else:raise AssertionError('Foreign run enqueued')
assert denials==4
env.cr.commit()
committed=[]
"""

FINAL="""
import hashlib
model=actor('alice','A');other=actor('bob','B')
ident=CAPTURE['run'];row=model._report_row(ident)
for key in ('cursor','total','points','snapshot','snapshot_digest','result_digest'):
    assert row[key]==CAPTURE['row'][key],key
assert row['cursor']==1200
result=run_once(env.registry,str(uuid4()),pool='bulk',workspace_id=FIXTURE['workspaces']['A']['id'])
assert result['state']=='completed',result
env.cr.rollback();env.invalidate_all()
state=model._report_status(ident)
assert state['state']=='completed' and state['cursor']==state['total']==1201 and state['points']==519600
row=model._report_row(ident);assert row['snapshot'] is None
assert model._start_report(row['request_first'],row['request_last'],'bx05-snapshot')==ident
assert not model._cancel_report(ident)
env.cr.execute("SELECT payload->'input'->>'cursor',result FROM mp_job WHERE handler='org.example.background:report_chunk' ORDER BY (payload->'input'->>'cursor')::int")
outputs=env.cr.fetchall();assert len(outputs)==13
assert [int(cursor) for cursor,result in outputs]==list(range(0,1201,100))
assert sum(result['count'] for cursor,result in outputs)==1201
previous='0'*64
for cursor,result in outputs:
    previous=hashlib.sha256(json.dumps([previous,result['digest']],separators=(',',':')).encode()).hexdigest()
assert previous==state['digest']
foreign=other.search([('name','like','BX05 foreign %')],order='id');assert len(foreign)==20
boundary=model._start_report(row['request_first'],foreign[-1].id,'bx05-scope-boundary')
boundary_row=model._report_row(boundary)
assert boundary_row['total']==1201 and all(item[0]<=row['request_last'] for item in boundary_row['snapshot'])
import psycopg2
try:
    with env.cr.savepoint():
        env['mp.background.report'].sudo().browse(boundary_row['id']).write(dict(snapshot=False))
        env.flush_all()
except psycopg2.IntegrityError:pass
else:raise AssertionError('Running snapshot constraint missing')
assert isinstance(model._report_row(boundary)['snapshot'],list)
assert model._cancel_report(boundary)
assert model._report_row(boundary)['snapshot'] is None
big=model.create([dict(name='BX05 heavy '+str(n),points=n%1000) for n in range(5001)])
env.cr.commit()
env.cr.execute('SELECT count(*) FROM mp_background_report');before,=env.cr.fetchone()
try:model._start_report(big[0].id,big[-1].id,'bx05-too-large')
except ValidationError:pass
else:raise AssertionError('Oversized snapshot accepted')
env.cr.execute('SELECT count(*) FROM mp_background_report');assert env.cr.fetchone()==(before,)
env.cr.commit()
print('BX04_RESULT='+json.dumps(dict(run=ident,count=1201,points=519600,chunks=13,digest=previous,
    partial_upgrade_preserved=True,snapshot_preserved_after_source_edit=True,terminal_snapshot_cleared=True,
    running_snapshot_constraint=True,range_excluded_foreign_rows=True,oversize_refused=True,
    big_first=big[0].id,big_last=big[-2].id)))
"""


def upgrade(probe,candidate):
    build=load(candidate);artifact=build['artifacts']['org.example.background'];assert artifact['version'] in ('0.3.0','0.3.1','0.3.2')
    path=probe.site.local/('bx05-upgrade-'+artifact['version'].replace('.','')+'.json')
    assert not path.exists() and not probe.operator._lanes()
    _,payload,_=assemble(ROOT,'plugins/background/plugin.toml')
    assert artifact['digest']=='sha256:'+hashlib.sha256(payload).hexdigest()
    trust_path=probe.site.private/'trust.json';trust=load(trust_path)
    assert artifact['digest'] not in trust['approved_digests']
    trust['approved_digests'].append(artifact['digest']);trust['generation']+=1;write(trust_path,trust)
    archive=probe.site.private/artifact['file'];assert not archive.exists();archive.write_bytes(payload)
    validator=configuration(trust_path);catalog=Catalog(probe.site.private/'catalog',validator)
    catalog.add(archive,expected_digest=artifact['digest'])
    executor=StagedNativeExecutor(probe.operator.store,probe.site.private/'target.json',probe.site.private/'catalog',validator)
    reader=executor.observer;observed=reader.read();rows=catalog.snapshot();before=reader.state(observed,rows)
    stages=StageStore(executor.store,executor.config,catalog)
    descriptor=stages.stage(build['image_id']);_,staged=stages.load(descriptor)
    installation=next(row for row in observed['sites'][0]['installations'] if row['plugin_id']=='org.example.background')['installation_id']
    targets=[dict(installation_id=installation,site_id=probe.state['site_id'],workspace_id=workspace['public_id'],
        plugin_id='org.example.background',action='upgrade') for workspace in probe.fixture['workspaces'].values()]
    operation=str(uuid4())
    bundle=prepare_staged_plan(before,observed['sites'],rows,staged['runtime'],descriptor,targets=targets,
        operation_type='upgrade',operation_id=operation,created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        base_runtime=observed['runtime'])
    validate=executor._validate();executor.store.register(bundle,validate)
    executor.store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
        acknowledgments=dict(destructive=False,trust_expansion=True,permission_expansion=False))
    write(path,dict(phase='applying',operation=operation,image=build['image_id']))
    result=executor.apply(operation)
    assert result['state']=='completed' and result['traffic_resumed']
    write(path,dict(phase='passed',operation=operation,image=build['image_id'],result=result))
    print(dict(phase='upgraded',operation=operation),flush=True)


def main(action,candidate):
    probe=Probe('bx-05-chunks-01')
    if action=='upgrade':upgrade(probe,candidate)
    elif action=='retry':
        path=probe.site.local/'bx05-reviewed-retry.json';assert not path.exists()
        job=probe.sql("SELECT job_public_id FROM mp_background_report WHERE request_key='bx05-snapshot'")
        assert probe.row(job)['state']=='dead_letter'
        review=probe.operator.run('review',job=job,action='retry')
        write(path,dict(phase='reviewed',job=job,review=review))
        result=probe.operator.run('apply',job=job,action='retry',approval=review['approval'])
        assert result['applied'] and probe.row(job)['state']=='retry'
        write(path,dict(phase='passed',job=job,review=review,result=result))
        print(dict(phase='retry_approved',job=job),flush=True)
    elif action=='finish-basic':
        path=probe.site.local/'bx05-basic-resume.json';assert not path.exists()
        assert load(probe.site.local/'bx05-reviewed-retry.json')['phase']=='passed'
        prefix=BASIC.split("model=actor('alice','A');other=actor('bob','B')",1)[0]
        source=prefix+RESUME+BASIC.split('committed=[]',1)[1]
        write(path,dict(phase='running',image=probe.state['image_id']))
        result=native(probe,'bx05-basic-resume',source)
        write(path,dict(phase='passed',image=probe.state['image_id'],result=result))
        print(dict(phase='basic_resume_passed',chunks=result['chunks']),flush=True)
    elif action=='finish-last':
        path=probe.site.local/'bx05-basic-final.json';assert not path.exists()
        prefix=BASIC.split("model=actor('alice','A');other=actor('bob','B')",1)[0]
        write(path,dict(phase='running',image=probe.state['image_id']))
        result=native(probe,'bx05-basic-final',prefix+FINAL,CAPTURE=load(probe.site.local/'bx05-finalization-gap.json'))
        write(path,dict(phase='passed',image=probe.state['image_id'],result=result))
        print(dict(phase='basic_final_passed',chunks=result['chunks']),flush=True)
    else:
        path=probe.site.local/'bx05-basic.json';assert not path.exists() and not probe.operator._lanes()
        write(path,dict(phase='running',image=probe.state['image_id']))
        result=native(probe,'bx05-basic',BASIC)
        write(path,dict(phase='passed',image=probe.state['image_id'],result=result))
        print(dict(phase='basic_passed',chunks=result['chunks'],scope_denials=result['scope_denials']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['upgrade','basic','retry','finish-basic','finish-last'])
    parser.add_argument('--candidate',type=Path);args=parser.parse_args();main(args.action,args.candidate)
