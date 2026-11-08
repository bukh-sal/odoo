"""Once-only approved registered Tasks repair on the retained AP pilot."""
import argparse
import base64
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools'),str(ROOT/'release'),str(ROOT/'packages/platform_sdk')]
from application_pilot import Pilot,load,write
from check_reference import Client
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image,DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore,prepare_staged_plan
from modular_platform.job_operator import JobOperator
from qualify_release_reader_rollout import files


def source_rows(client,seed):
    return dict(list=client.native('mp.aurora.task.list','read',[[seed['list']],['name','owner_id','member_ids','description']],workspace=None),
        tasks=client.native('mp.aurora.task','read',[seed['tasks'],['name','description','list_id','stage_id','creator_id','assignee_id','due_date','reminder','reminder_revision']],workspace=None))


def queue(site,seed,label):
    state=site.state();target=load(site.private/'target.json');state.update(database=target['sites'][0]['database'])
    sql="SELECT jsonb_build_object('id',j.public_id,'actor',j.actor_id,'workspace',j.workspace_id,'installation',j.installation_id,'payload',j.payload,'key',j.idempotency_key,'digest',j.input_digest,'at',j.available_at,'deadline',j.deadline_at,'state',j.state,'attempts',j.attempts) FROM mp_aurora_reminder r JOIN mp_job j ON j.public_id=r.job_id WHERE r.task_id="+str(seed['tasks'][0])+";"
    return json.loads(site.sql(state,label,sql))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['seed','continue_seed','prepare','drain_workers','apply','verify']);p.add_argument('--run',default='ap01-pilot-01')
    p.add_argument('--port',type=int,default=18172);a=p.parse_args();site=Pilot(a)
    marker=site.local/'repair-operation.json';seedpath=site.local/'repair-seed.json'
    if a.phase in {'seed','continue_seed'}:
        assert load(site.private/'target.json')['image_id']=='sha256:cac49d72605fe62a13b262c4775a0c55da6052f1743fb2b6d6b667a8a877de7f'
        c=Client(site,'alice');fixture=load(site.local/'fixtures.json')
        if a.phase=='seed':
            assert not seedpath.exists()
            assert c.native('mp.aurora.task.list','search_count',[[]],workspace=None)==0
            seed=dict(phase='creating_list');write(seedpath,seed)
            listing,=c.native('mp.aurora.task.list','create',[[dict(name='Workshop baseline for app upgrade',
                description='Fictional original app data; preserve through a real registered-app upgrade',
                member_ids=[(6,0,[fixture['users']['bob']['id']])])]],workspace=None)
        else:
            seed=load(seedpath);assert seed['phase']=='creating_tasks' and seed['list']==[1]
            assert load(site.local/'repair-seed-diagnosis.json')['tasks']==0
            assert c.native('mp.aurora.task','search_count',[[]],workspace=None)==0
            listing,=seed['list']
            row,=c.native('mp.aurora.task.list','read',[[listing],['name','owner_id']],workspace=None)
            assert row['name']=='Workshop baseline for app upgrade' and row['owner_id'][0]==fixture['users']['alice']['id']
        seed.update(phase='creating_tasks',list=listing);write(seedpath,seed)
        due=(datetime.now(timezone.utc)+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        tasks=c.native('mp.aurora.task','create',[[dict(name='Review equipment checklist',list_id=listing,
            assignee_id=fixture['users']['operator']['id'],due_date=due,reminder='0'),
            dict(name='Collect inspection sheets',list_id=listing,description='Original unassigned task')]],workspace=None)
        seed.update(phase='creating_file',tasks=tasks);write(seedpath,seed)
        attachment,=c.native('ir.attachment','create',[[dict(name='AP original brief.txt',res_model='mp.aurora.task',res_id=tasks[0],
            datas=base64.b64encode(b'Fictional workshop brief retained across app-only upgrade.').decode(),mimetype='text/plain')]],workspace=None)
        seed.update(phase='seeded',attachment=attachment,rows=source_rows(c,seed),queue=queue(site,seed,'repair-source-queue'))
        assert seed['queue']['state']=='pending' and seed['queue']['attempts']==0 and seed['queue']['workspace'] is None
        write(seedpath,seed)
    elif a.phase=='prepare':
        assert not marker.exists();assert load(seedpath)['phase']=='seeded'
        candidate=load(ROOT/'docs/evidence/post-r1/application-adoption/ap01-defaults-image02.json');assert candidate['state']=='verified'
        trust=site.private/'trust.json';policy=load(trust);assert policy['generation']==1 and candidate['artifact_digest'] not in policy['approved_digests']
        write(site.local/'repair-curation.json',dict(previous=policy,new_digest=candidate['artifact_digest'],source_review='ADR0078; independent app commitdb32b467; two field defaults, preserved server ownership'))
        policy['generation']+=1;policy['approved_digests']=sorted([*policy['approved_digests'],candidate['artifact_digest']]);write(trust,policy)
        validator=configuration(trust);catalog=Catalog(site.private/'catalog',validator)
        catalog.add(ROOT/'.local/application-adoption/artifacts/dev.aurora.tasks-0.2.3.mplug',expected_digest=candidate['artifact_digest'])
        native=StagedNativeExecutor(OperatorStore(site.private/'control'),site.private/'target.json',site.private/'catalog',validator)
        before=inspect_image(native.config['image_id']);after=inspect_image(candidate['image_id'])
        descriptor=StageStore(native.store,native.config,catalog).stage(candidate['image_id'])
        observed=native.observer.read();snapshot=catalog.snapshot();document=native.observer.state(observed,snapshot)
        current,=document['state']['installations'];assert current['plugin_id']=='dev.aurora.tasks' and current['workspace_id'] is None
        target={k:current[k] for k in ('installation_id','site_id','workspace_id','plugin_id')};target['action']='upgrade'
        bundle=prepare_staged_plan(document,observed['sites'],snapshot,after,descriptor,targets=[target],operation_type='upgrade',
            operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=before)
        assert bundle['plan']['backup']['required']
        record=dict(phase='registering',operation=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],
            candidate=candidate['image_id'],base=native.config,files=files(native.observer),queue=queue(site,load(seedpath),'repair-before-plan-queue'))
        write(marker,record);validate=native._validate();native.store.register(bundle,validate)
        review=native.store.review(record['operation'],validate)
        approval=native.store.approve(record['operation'],exact_hash=record['plan_hash'],noninteractive=True,revalidate=validate,
            acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=True))
        record.update(phase='approved',review_digest=data_digest(review),approval_digest=data_digest(approval));write(marker,record)
    else:
        record=load(marker)
        native=StagedNativeExecutor(OperatorStore(site.private/'control'),site.private/'target.json',site.private/'catalog',configuration(site.private/'trust.json'))
        if a.phase=='drain_workers':
            assert record['phase']=='applying'
            status=native.store.status(record['operation'])
            assert status['state']=='approved' and status['phase']=='prepared' and not status['mutation_started']
            path=site.local/'repair-drain.json';assert not path.exists()
            result=JobOperator(native.store,site.private/'target.json').run('drain');assert result['state']=='paused'
            write(path,result);record.update(phase='approved',explicit_worker_drain_completed=True);write(marker,record)
        elif a.phase=='apply':
            assert record['phase']=='approved';record['phase']='applying';write(marker,record)
            result=native.apply(record['operation']);assert result['state']=='completed' and result['traffic_resumed']
            record.update(phase='applied');write(marker,record)
        else:
            assert record['phase']=='applied';target=load(site.private/'target.json');assert target['image_id']==record['candidate']
            c=Client(site,'alice');seed=load(seedpath);assert source_rows(c,seed)==seed['rows']
            assert queue(site,seed,'repair-after-queue')==record['queue']
            assert all(files(DockerObserver(target)).get(k)==v for k,v in record['files'].items())
            uid=load(site.local/'fixtures.json')['users']['alice']['id']
            assert c.native('mp.aurora.task.list','default_get',[['owner_id']],workspace=None)==dict(owner_id=uid)
            assert c.native('mp.aurora.task','default_get',[['creator_id']],workspace=None)==dict(creator_id=uid)
            state=site.state();state.update(image_id=target['image_id'],inventory_digest=inspect_image(target['image_id'])['inventory_digest'],database=target['sites'][0]['database'])
            site.phase(state,'pilot_ready')
            record.update(phase='verified',original_rows_and_files_preserved=True,pending_native_job_identity_preserved=True,
                default_owner_and_creator_current_user=True,foundation_platform_version='0.1.49')
            write(marker,record)
    print(json.dumps(dict(phase=a.phase,result=load(seedpath)['phase'] if a.phase in {'seed','continue_seed'} else load(marker)['phase'])))


if __name__=='__main__':main()
