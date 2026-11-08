"""AP-G/H real registered app publication/fault/fresh recovery on an owned sibling."""
import argparse
import base64
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'release'),str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from application_adoption_site import AdoptionSite,load,write
from check_reference import Client
from aurora_tasks_publication import SEED,VERIFY,snapshot
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image,DockerObserver
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest
from modular_platform.release_staging import StageStore,prepare_staged_plan
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.job_operator import JobOperator
from qualify_release_reader_rollout import files


def runtime(site):
    return StagedNativeExecutor(OperatorStore(site.private/'control'),site.private/'target.json',site.private/'catalog',configuration(site.private/'trust.json'))


def sync(site):
    state=site.state();target=load(site.private/'target.json')
    state.update(image_id=target['image_id'],database=target['sites'][0]['database'],inventory_digest=inspect_image(target['image_id'])['inventory_digest'])
    write(site.local/'state.json',state);return state


def business(site, profile='tasks'):
    state=sync(site)
    tables=['mp_aurora_task_list','mp_aurora_task_stage','mp_aurora_task','mp_aurora_notification']
    if profile=='projects':
        tables+=['mp_aurora_project','mp_aurora_project_member_rel','mp_aurora_project_task_link']
    projection = "to_jsonb(r)-'target_date' ORDER BY (to_jsonb(r)-'target_date')::text" if profile=='projects' else 'to_jsonb(r) ORDER BY id'
    query='SELECT jsonb_build_object('+','.join("'"+t+"',(SELECT jsonb_agg("+projection+") FROM "+t+' r)' for t in tables)+');'
    return data_digest(json.loads(site.sql(state,'business-'+str(time.monotonic_ns()),query)))


def native_result(site,label,code):
    raw=site.native(sync(site),label,[],code)
    return next(json.loads(r.split('=',1)[1]) for r in raw.decode().splitlines() if r.startswith('MP_AT_PUBLICATION='))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['seed','prepare','apply','fault','revoke','restore','resume','effects'])
    p.add_argument('--run',default='ap02-release-01');p.add_argument('--port',type=int,default=18173)
    p.add_argument('--profile',choices=['tasks','projects'],default='tasks')
    p.add_argument('--candidate',type=Path,help='Explicit independently composed Projects app-set receipt')
    p.add_argument('--label',choices=['fault','forward'],default='fault');a=p.parse_args();site=AdoptionSite(a)
    path=site.local/(a.label+'-operation.json');seedpath=site.local/(a.label+'-seed.json')
    native=runtime(site);state=sync(site)
    if a.phase=='seed':
        assert not seedpath.exists();write(seedpath,dict(phase='creating_original_work'))
        original = 'sha256:8d61e6cc5f1a0c8cc5d1ee262cfa6f9abf9c225732e6d50e59909b76cd51451c' if a.profile=='projects' else 'sha256:cac49d72605fe62a13b262c4775a0c55da6052f1743fb2b6d6b667a8a877de7f'
        assert native.config['image_id']==original
        if a.profile=='projects':assert load(site.local/'integration-contract.json')['phase']=='passed'
        assert not JobOperator(native.store,site.private/'target.json')._lanes()
        seed=native_result(site,a.label+'-pending-seed','FIXTURE='+repr(load(site.local/'fixtures.json'))+'\n'+SEED)
        seed['phase']='pending_and_claimed';write(seedpath,seed)
        c=Client(site,'alice')
        attachment,=c.native('ir.attachment','create',[[dict(name='Original application brief '+a.label+'.txt',res_model='mp.aurora.task',res_id=seed['tasks'][0],datas=base64.b64encode(b'Original fictional app-only release file witness.').decode(),mimetype='text/plain')]],workspace=None)
        if a.label=='fault':
            fixture=load(site.local/'fixtures.json')
            listing=c.native('mp.aurora.task','read',[[seed['tasks'][0]],['list_id']],workspace=None)[0]['list_id'][0]
            c.native('mp.aurora.task.list','write',[[listing],dict(member_ids=[(6,0,[fixture['users']['bob']['id']])])],workspace=None)
            bob=Client(site,'bob')
            task,=bob.native('mp.aurora.task','create',[[dict(name='Original actor revoked after checkpoint',list_id=listing,
                assignee_id=fixture['users']['operator']['id'],due_date=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),reminder='0')]],workspace=None)
            seed['revoked_actor_task']=task
            seed['revoked_actor_job']=site.sql(state,'original-bob-job','SELECT job_id FROM mp_aurora_reminder WHERE task_id='+str(task)+';').decode().strip()
        if a.profile=='projects':
            project=load(site.local/'integration-contract.json')['records']['project']
            link,=c.native('mp.aurora.project.task.link','create',[[dict(project_id=project,task_id=seed['tasks'][0],note='Pending reminder linked to original project')]],workspace=None)
            project_file,=c.native('ir.attachment','create',[[dict(name='Original project brief '+a.label+'.txt',res_model='mp.aurora.project',res_id=project,datas=base64.b64encode(b'Original fictional project recovery witness.').decode(),mimetype='text/plain')]],workspace=None)
            seed.update(project=project,link=link,project_attachment=project_file)
        seed.update(phase='seeded',attachment=attachment,before=snapshot(site,state,seed['jobs']),business=business(site,a.profile),files=files(native.observer));write(seedpath,seed)
    elif a.phase=='prepare':
        assert not path.exists();assert load(seedpath)['phase']=='seeded'
        if a.candidate and a.profile!='projects':raise ValueError('Explicit candidate is bounded to the Projects qualification profile')
        candidate=load(a.candidate or ROOT/'docs/evidence/post-r1/application-adoption'/('ap03-projects-tasks-011-01-image.json' if a.profile=='projects' else 'ap01-defaults-image02.json'));assert candidate['state']=='verified'
        plugin='dev.aurora.projects' if a.profile=='projects' else 'dev.aurora.tasks'
        artifact=next(row['digest'] for row in candidate['applications'] if row['plugin_id']==plugin) if a.profile=='projects' else candidate['artifact_digest']
        trust=load(site.private/'trust.json')
        incoming = [r for r in candidate['applications'] if r['plugin_id'] in {'dev.aurora.projects','dev.aurora.projects_tasks'}] if a.profile=='projects' else [dict(plugin_id=plugin,version='0.2.3',digest=artifact)]
        missing=[r for r in incoming if r['digest'] not in trust['approved_digests']]
        if missing:
            trust['generation']+=1;trust['approved_digests']=sorted(set(trust['approved_digests'])|{r['digest'] for r in missing});write(site.private/'trust.json',trust)
            cat=Catalog(site.private/'catalog',configuration(site.private/'trust.json'))
            for row in missing:
                cat.add(ROOT/'.local/application-adoption/artifacts'/(row['plugin_id']+'-'+row['version']+'.mplug'),expected_digest=row['digest'])
        native=runtime(site);catalog=Catalog(native.catalog_root,native.validator,readonly=True)
        before=inspect_image(native.config['image_id']);after=inspect_image(candidate['image_id'])
        assert before['platform_version']==after['platform_version']=='0.1.49'
        descriptor=StageStore(native.store,native.config,catalog).stage(candidate['image_id'])
        observed=native.observer.read();snapshot_=catalog.snapshot();document=native.observer.state(observed,snapshot_)
        current,=[i for i in document['state']['installations'] if i['plugin_id']==plugin];assert current['state']=='installed'
        manifest,=[m for m in document['state']['release_lock']['plugins'] if m['plugin_id']==plugin]
        assert manifest['version']==('0.1.0' if a.profile=='projects' else '0.2.2')
        if a.profile=='projects':
            assert {i['plugin_id'] for i in document['state']['installations']}=={'dev.aurora.projects','dev.aurora.tasks','dev.aurora.projects_tasks'}
            assert before['inventory']['artifacts']['dev.aurora.tasks']==after['inventory']['artifacts']['dev.aurora.tasks']
        target={k:current[k] for k in ('installation_id','site_id','workspace_id','plugin_id')};target['action']='upgrade'
        targets=[target]
        if a.profile=='projects' and before['inventory']['artifacts']['dev.aurora.projects_tasks']!=after['inventory']['artifacts']['dev.aurora.projects_tasks']:
            extension,=[i for i in document['state']['installations'] if i['plugin_id']=='dev.aurora.projects_tasks']
            targets.append(dict({k:extension[k] for k in ('installation_id','site_id','workspace_id','plugin_id')},action='upgrade'))
        bundle=prepare_staged_plan(document,observed['sites'],snapshot_,after,descriptor,targets=targets,operation_type='upgrade',operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=before)
        assert bundle['plan']['backup']['required']
        record=dict(phase='registering',operation=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],base=native.config,candidate=candidate['image_id'],business=business(site,a.profile),files=files(native.observer),profile=a.profile)
        write(site.local/(a.label+'-bundle.json'),bundle)
        write(path,record);validate=native._validate();native.store.register(bundle,validate)
        review=native.store.review(record['operation'],validate)
        approval=native.store.approve(record['operation'],exact_hash=record['plan_hash'],noninteractive=True,revalidate=validate,acknowledgments=dict(destructive=True,trust_expansion=True,permission_expansion=True))
        record.update(phase='approved',review_digest=data_digest(review),approval_digest=data_digest(approval));write(path,record)
    else:
        record=load(path);operation=record['operation'];seed=load(seedpath)
        if a.phase in {'apply','fault'}:
            assert record['phase']=='approved';record['phase']='applying';write(path,record)
            if a.phase=='fault':
                assert a.label=='fault';advance=native.store.advance
                def inject(op,locks,phase,**details):
                    result=advance(op,locks,phase,**details)
                    if op==operation and phase=='release_published':raise OperatorError('AP controlled app publication failure')
                    return result
                with patch.object(native.store,'advance',side_effect=inject):
                    try:native.apply(operation)
                    except OperatorError as error:assert 'AP controlled app publication failure' in str(error),str(error)
                    else:raise AssertionError('Publication fault not reached')
                status=native.store.status(operation);assert status['state']=='recovery_required' and status['mutation_started'] and not status['traffic_resumed']
                failed=load(site.private/'target.json');site.command('stop-failed-app',['docker','stop',failed['worker_id']])
                journal=json.loads(site.command('independent-journal',[sys.executable,'-I',str(ROOT/'tools/modular.py'),'--config',str(site.private/'trust.json'),'operations','--store',str(native.store.root),'show',operation]))
                assert journal['state']=='recovery_required'
                record.update(phase='recovery_required',failed_app_stopped=True,failure_phase=status['phase'],independent_journal=True)
            else:
                result=native.apply(operation);assert result['state']=='completed' and result['traffic_resumed']
                sync(site);assert business(site,a.profile)==record['business']
                assert files(DockerObserver(load(site.private/'target.json')))==record['files']
                after=snapshot(site,sync(site),seed['jobs'])
                for ident,old in seed['before'].items():
                    now=dict(after[ident]);old=dict(old);now.pop('at');old.pop('at');assert now==old
                check=native_result(site,'forward-stale','SAVED='+repr(seed)+'\n'+VERIFY);assert check['stale_original_native_claim_denied']
                if a.profile=='projects':
                    alice=Client(site,'alice');projects=alice.native('mp.aurora.project','search_read',[[]],dict(fields=['target_date']),workspace=None)
                    assert projects and all(row['target_date'] is False for row in projects)
                    assert alice.native('mp.aurora.project','write',[[seed['project']],dict(target_date='2026-01-01')],workspace=None)
                    assert alice.native('mp.aurora.project','search_count',[[('target_date','<','2026-11-09'),('status','in',['planned','active','on_hold'])]],workspace=None)>=1
                    assert alice.native('mp.aurora.project.task.link','action_open_task',[[seed['link']]],workspace=None)['res_id']==seed['tasks'][0]
                    record['new_nullable_date_and_existing_native_integration_work']=True
                record.update(phase='published_verified',original_rows_files_preserved=True,job_identity_actor_payload_logical_schedule_deadline_preserved=True,stale_original_claim_denied=True)
        elif a.phase=='revoke':
            assert record['phase']=='recovery_required'
            bob=load(site.local/'fixtures.json')['users']['bob']['id']
            raw=site.sql(sync(site),'post-checkpoint-revoke',"BEGIN; UPDATE res_users SET active=false WHERE id="+str(bob)+" AND active RETURNING id; UPDATE mp_principal SET state='suspended' WHERE user_id="+str(bob)+" RETURNING state; COMMIT;")
            assert raw.strip()==(str(bob)+'\nsuspended').encode()
            record.update(phase='revoked_after_checkpoint',current_bob_deactivated=True)
            # The retained pilot is an independent deployment and stays useful.
            from application_pilot import Pilot
            pilot=Pilot(argparse.Namespace(run='ap01-pilot-01',port=18172));peer=Client(pilot,'alice')
            assert peer.native('mp.aurora.task','write',[[2],dict(description='Useful pilot work during independent app recovery')],workspace=None)
            record['pilot_useful_while_sibling_down']=True
        elif a.phase=='restore':
            assert record['phase']=='revoked_after_checkpoint';recovery=RestoreExecutor(native);decision=recovery.prepare(operation)
            record.update(phase='restoring',restore_digest=data_digest(decision));write(path,record)
            result=recovery.execute(decision,exact_hash=data_digest(decision),noninteractive=True)
            assert result['state']=='restored_verified' and result['keep_traffic_closed']
            target=load(site.private/'target.json');assert target['image_id']==record['base']['image_id'] and target['sites'][0]['database']!=record['base']['sites'][0]['database']
            sync(site);assert business(site,a.profile)==record['business'] and files(DockerObserver(target))==record['files']
            if a.profile=='projects':
                assert site.sql(sync(site),'restored-old-project-schema',"SELECT count(*) FROM information_schema.columns WHERE table_name='mp_aurora_project' AND column_name='target_date';").strip()==b'0'
            bob=load(site.local/'fixtures.json')['users']['bob']['id']
            assert site.sql(sync(site),'restored-current-native-auth','SELECT active FROM res_users WHERE id='+str(bob)+';').strip()==b'f'
            check=native_result(site,'restored-stale','SAVED='+repr(seed)+'\n'+VERIFY);assert check['stale_original_native_claim_denied']
            record.update(phase='restored_closed',fresh_database=target['sites'][0]['database'],exact_original_application_rows_files=True,current_native_auth_revocation_preserved=True,stale_original_claim_denied=True)
        elif a.phase=='resume':
            assert record['phase']=='restored_closed';recovery=RestoreExecutor(native);decision=recovery.prepare_resume(operation)
            record.update(phase='resuming',resume_digest=data_digest(decision));write(path,record)
            recovery.resume(decision,exact_hash=data_digest(decision),noninteractive=True);assert native.store.status(operation)['state']=='revoked'
            sync(site);alice=Client(site,'alice')
            assert alice.native('mp.aurora.task','write',[[seed['tasks'][0]],dict(description='Useful edit of original recovered task')],workspace=None)
            if a.profile=='projects':
                assert alice.native('mp.aurora.project','write',[[seed['project']],dict(description='Recovered inspection planning continues')],workspace=None)
                assert alice.native('mp.aurora.project.task.link','write',[[seed['link']],dict(note='Recovered linked work continues')],workspace=None)
                assert alice.native('mp.aurora.project.task.link','action_open_task',[[seed['link']]],workspace=None)['res_id']==seed['tasks'][0]
                record['useful_original_project_and_link_edit_open']=True
            try:Client(site,'bob')
            except AssertionError:pass
            else:raise AssertionError('Restored current-deactivated user logged in')
            record.update(phase='resumed',separate_resume=True,useful_original_record_edit=True,inactive_user_login_denied=True)
        elif a.phase=='effects':
            assert record['phase'] in {'resumed','published_verified'}
            op=JobOperator(native.store,site.private/'target.json');review=op.run('profile-review',urgent_lanes=1,bulk_lanes=1,shutdown_seconds=5)
            record.update(phase='starting_effects',profile_approval=review['approval']);write(path,record)
            assert op.run('profile-apply',approval=review['approval'])['state']=='ready'
            ids=','.join("'"+j+"'" for j in seed['jobs'])
            effect_state=sync(site)
            for _ in range(60):
                rows=json.loads(site.sql(effect_state,'effects-'+str(time.monotonic_ns()),"SELECT jsonb_agg(jsonb_build_object('id',public_id,'state',state,'attempts',attempts,'result',result)) FROM mp_job WHERE public_id IN ("+ids+");"))
                if all(row['state'] in {'completed','held','failed','dead_letter','cancelled'} for row in rows):break
                time.sleep(1)
            assert len(rows)==2 and all(row['state']=='completed' and row['result']==dict(outcome='notified') for row in rows),rows
            for row in rows:assert row['attempts']==(2 if row['id']==seed['jobs'][0] else 1),rows
            taskids=','.join(map(str,seed['tasks']))
            assert site.sql(sync(site),'effect-count-'+a.label,'SELECT count(*),count(DISTINCT task_id) FROM mp_aurora_notification WHERE task_id IN ('+taskids+');').strip()==b'2|2'
            if 'revoked_actor_job' in seed:
                assert site.sql(effect_state,'revoked-actor-effect',"SELECT state,attempts,error_code FROM mp_job WHERE public_id='"+seed['revoked_actor_job']+"';").strip()==b'held|0|FORBIDDEN'
                assert site.sql(effect_state,'revoked-actor-no-notice','SELECT count(*) FROM mp_aurora_notification WHERE task_id='+str(seed['revoked_actor_task'])+';').strip()==b'0'
                record['revoked_original_actor_stays_held_without_effect']=True
            drained=op.run('drain');assert drained['state']=='paused'
            record.update(phase='verified',effects=2,exact_attempts=True,final_drain=drained)
        write(path,record)
    print(json.dumps(dict(phase=a.phase,label=a.label,result=load(seedpath)['phase'] if a.phase=='seed' else load(path)['phase'])),flush=True)

if __name__=='__main__':main()
