"""Phase-recorded setup for BX-04's hot and 70-workspace native workload."""
import argparse
from datetime import datetime,timezone
import json
import hashlib
from pathlib import Path
from uuid import uuid4

from background_lifecycle import shell
from background_site import load,write,Catalog,configuration,prepare_current_install_targets,ROOT
from background_workers import Probe
from modular_platform.native_executor import NativeExecutor
from modular_platform.native_executor import StagedNativeExecutor
from modular_platform.release_staging import StageStore,prepare_staged_plan
from reference_package import assemble


CREATE="""
import json
assert env.cr.dbname==EXPECTED_DB
env.cr.execute('SELECT id FROM mp_principal WHERE public_id=%s',[FIXTURE['users']['alice']['principal_id']])
principal,=env.cr.fetchone()
result=dict(FIXTURE['workspaces'])
for number in range(2,70):
    label='W'+str(number).zfill(2)
    workspace=env['mp.workspace'].create(dict(name='BX-04 '+label))
    env['mp.membership'].create(dict(principal_id=principal,workspace_id=workspace.id,role='editor'))
    result[label]=dict(id=workspace.id,public_id=workspace.public_id)
env.cr.commit()
print('BX04_RESULT='+json.dumps(result))
"""

DATA="""
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
import json
assert env.cr.dbname==EXPECTED_DB
result={}
for label,workspace in WORKSPACES.items():
    who='bob' if label=='B' else 'alice'
    actor=scoped_environment(api.Environment(env.cr,FIXTURE['users'][who]['id'],{}),workspace['public_id'])
    rows=actor['mp.background.task'].create([dict(name='BX-04 report '+label+' '+str(n),points=n) for n in range(10)])
    assert len(rows)==10 and rows[-1].id-rows[0].id==9
    result[label]=dict(workspace,first=rows[0].id,last=rows[-1].id,points=sum(range(10)),count=10,user=who)
env.cr.commit()
print('BX04_RESULT='+json.dumps(result))
"""


def native(probe,tag,source,**inputs):
    code='EXPECTED_DB='+repr(probe.state['database'])+'\nFIXTURE='+repr(probe.fixture)+'\n'
    code+='\n'.join(key+'='+repr(value) for key,value in inputs.items())+'\n'+source
    raw=shell(probe,tag,code)
    result,=[json.loads(line.split('=',1)[1]) for line in raw.splitlines() if line.startswith('BX04_RESULT=')]
    return result


def run(phase,candidate=None):
    probe=Probe('bx-04-capacity-01')
    path=probe.site.local/'bx04-sustained-setup.json'
    record=load(path) if path.exists() else {}
    if phase=='workspaces':
        assert not record and load(probe.site.local/'bg04-load-one-urgent.json')['phase']=='passed'
        assert not probe.operator._lanes()
        write(path,dict(phase='creating_workspaces'))
        workspaces=native(probe,'bx04-create-workspaces',CREATE)
        assert len(workspaces)==70
        record=dict(phase='workspaces_created',workspaces=workspaces)
    elif phase=='activate':
        assert record['phase']=='workspaces_created' and not probe.operator._lanes()
        validator=configuration(probe.site.private/'trust.json')
        catalog=Catalog(probe.site.private/'catalog',validator,readonly=True)
        reader=probe.operator.reader;observed=reader.read();rows=catalog.snapshot()
        installation=next(row for row in observed['sites'][0]['installations'] if row['plugin_id']=='org.example.background')['installation_id']
        targets=[dict(installation_id=installation,site_id=probe.state['site_id'],workspace_id=workspace['public_id'],
            plugin_id='org.example.background',action='install') for label,workspace in record['workspaces'].items() if label not in ('A','B')]
        operation=str(uuid4())
        bundle=prepare_current_install_targets(reader.state(observed,rows),observed['sites'],rows,
            activation_targets=targets,operation_id=operation,created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        executor=NativeExecutor(probe.operator.store,probe.site.private/'target.json',probe.site.private/'catalog',validator)
        validate=executor._validate();executor.store.register(bundle,validate)
        executor.store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
            acknowledgments=dict(destructive=False,trust_expansion=True,permission_expansion=True))
        record.update(phase='activating',operation=operation,plan_hash=bundle['plan_hash']);write(path,record)
        result=executor.apply(operation)
        assert result['state']=='completed' and result['traffic_resumed']
        record.update(phase='activated',result=result)
    elif phase=='data':
        assert record['phase']=='activated'
        record.update(phase='creating_data');write(path,record)
        data=native(probe,'bx04-sustained-data',DATA,WORKSPACES=record['workspaces'])
        assert len(data)==70
        record.update(phase='data_ready',data=data)
    elif phase=='upgrade-reference':
        assert record['phase']=='data_ready' and not probe.operator._lanes()
        build=load(candidate);artifact=build['artifacts']['org.example.background']
        assert artifact['version']=='0.2.1'
        _,payload,_=assemble(ROOT,'plugins/background/plugin.toml')
        assert artifact['digest']=='sha256:'+hashlib.sha256(payload).hexdigest()
        trust_path=probe.site.private/'trust.json';trust=load(trust_path)
        assert artifact['digest'] not in trust['approved_digests']
        trust['approved_digests'].append(artifact['digest']);trust['generation']+=1
        write(trust_path,trust)
        archive=probe.site.private/artifact['file'];assert not archive.exists();archive.write_bytes(payload)
        validator=configuration(trust_path);catalog=Catalog(probe.site.private/'catalog',validator)
        catalog.add(archive,expected_digest=artifact['digest'])
        executor=StagedNativeExecutor(probe.operator.store,probe.site.private/'target.json',probe.site.private/'catalog',validator)
        reader=executor.observer;observed=reader.read();rows=catalog.snapshot()
        before=reader.state(observed,rows)
        stages=StageStore(executor.store,executor.config,catalog)
        descriptor=stages.stage(build['image_id']);_,staged=stages.load(descriptor)
        installation=next(row for row in observed['sites'][0]['installations'] if row['plugin_id']=='org.example.background')['installation_id']
        targets=[dict(installation_id=installation,site_id=probe.state['site_id'],workspace_id=workspace['public_id'],
            plugin_id='org.example.background',action='upgrade') for workspace in record['workspaces'].values()]
        operation=str(uuid4())
        bundle=prepare_staged_plan(before,observed['sites'],rows,staged['runtime'],descriptor,
            targets=targets,operation_type='upgrade',operation_id=operation,
            created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),base_runtime=observed['runtime'])
        validate=executor._validate();executor.store.register(bundle,validate)
        executor.store.approve(operation,exact_hash=bundle['plan_hash'],noninteractive=True,revalidate=validate,
            acknowledgments=dict(destructive=False,trust_expansion=True,permission_expansion=False))
        record.update(phase='upgrading_reference',reference_operation=operation,reference_candidate=build['image_id']);write(path,record)
        result=executor.apply(operation)
        assert result['state']=='completed' and result['traffic_resumed']
        record.update(phase='reference_upgraded',reference_result=result)
    elif phase=='retire-failed-hot':
        failed_path=probe.site.local/'bx04-sustained-hot.json';failed=load(failed_path)
        assert failed['phase']=='idle_measured' and 'cleanup' not in failed
        drained=probe.operator.run('drain');assert drained['state']=='paused' and not probe.operator._lanes()
        result=native(probe,'bx04-retire-failed-hot',"""
import json
from modular_platform import durable
assert env.cr.dbname==EXPECTED_DB
env.cr.execute('SELECT public_id,actor_id,workspace_id,effect_mode,state FROM mp_job WHERE public_id=ANY(%s)',[JOBS])
rows=env.cr.fetchall();assert len(rows)==222
for ident,actor,workspace,effect,state in rows:
    assert effect=='idempotent' and state not in ('running','outcome_unknown')
    durable.cancel_scheduled(env.cr,ident,actor_id=actor,workspace_id=workspace)
env.cr.commit()
env.cr.execute('SELECT state,count(*) FROM mp_job WHERE public_id=ANY(%s) GROUP BY state',[JOBS])
states=dict(env.cr.fetchall());assert set(states)<={'cancelled','completed','dead_letter'}
print('BX04_RESULT='+json.dumps(dict(states=states,owned_jobs=222)))
""",JOBS=list(failed['seed']['jobs']))
        failed.update(phase='harness_disconnected_retired',cleanup=result,
            diagnostic='RemoteDisconnected at first mixed request after idle scheduled wait; warm connections expired. No sustained-load pass claimed.')
        write(failed_path,failed)
    else:raise ValueError(phase)
    write(path,record)
    print(json.dumps(dict(phase=record['phase'],workspaces=len(record['workspaces']),operation=record.get('operation'))),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['workspaces','activate','data','upgrade-reference','retire-failed-hot'])
    parser.add_argument('--candidate',type=Path)
    args=parser.parse_args();run(args.phase,args.candidate)
