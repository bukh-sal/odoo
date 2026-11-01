"""Actual installed native feature lifecycle; no handler/source substitution."""
import argparse,copy,hashlib,json,sys,tarfile
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.native_feature_executor import NativeFeatureExecutor
from modular_platform.lifecycle_planning import prepare_current_feature
from modular_platform.operator_store import OperatorStore
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.restore_continuation import FILE_OBSERVATION
f=j.f;f.OUTPUT=OUT
TABLES=['mp_example_note','mp_example_canvas_board','mp_example_note_event_summary','mp_plugin_installation',
    'mp_workspace_plugin','mp_service_binding','mp_plugin_grant','mp_service_credential','mp_workspace','mp_membership',
    'mp_principal','mp_outbox','mp_event_subscription','mp_event_delivery','mp_event_consumption','mp_event_consumer_state','mp_job']

def context():
    state=f.load(j.LOCAL/'state.json');f.guard(state)
    native=NativeFeatureExecutor(OperatorStore(j.LOCAL/'operator/control'),j.LOCAL/'operator/target.json',j.LOCAL/'operator/catalog',configuration(j.LOCAL/'operator/trust.json'))
    return state,native

def snapshot(state,label):
    query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SELECT jsonb_build_object("
    query+=','.join("'"+t+"',COALESCE((SELECT jsonb_agg(to_jsonb(t) ORDER BY id) FROM "+t+" t),'[]'::jsonb)" for t in TABLES)
    return json.loads(f.sql(state,label,query+'); ROLLBACK;'))

def native_probe(state,native,label,expected):
    fixture=f.load(j.LOCAL/'fixtures.json')
    code='import json\nfrom odoo import api\nfrom odoo.exceptions import AccessError\nfrom odoo.addons.mp_identity.scopes import scoped_environment\nfrom odoo.addons.mp_core.controllers import PublicError\n'
    code+='FIXTURE='+repr(fixture)+'\nexpected='+repr(expected)+'\nresults={}\n'
    code+='for name in ["A","B","C"]:\n ws=FIXTURE["workspaces"][name]["public_id"]\n native=scoped_environment(api.Environment(env.cr,FIXTURE["users"]["alice"]["id"],{}),ws)\n model=native["mp.example.note"]\n try:\n  count=model.search_count([])\n  if name=="C" and expected=="suspended":raise AssertionError("Suspended native records were readable")\n  views=model.get_views([(False,"list"),(False,"form")],options={})\n  assert set(views["views"])=={"list","form"}\n  assert "<list" in views["views"]["list"]["arch"] and "<form" in views["views"]["form"]["arch"]\n  results[name]=dict(state="available",records=count,native_list_form=True)\n except (AccessError,PublicError) as error:\n  assert name=="C" and expected=="suspended"\n  results[name]=dict(state="denied",code=getattr(error,"code","FORBIDDEN"))\nenv.cr.rollback();print("MP_NATIVE_FEATURE_UI="+json.dumps(results))\n'
    raw=f.command(label,['docker','exec','-i',native.observer._container('app'),'/venv/bin/python','odoo-bin','shell',
        '-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0'],input=code.encode())
    rows=[json.loads(line.split('=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_NATIVE_FEATURE_UI=')]
    assert len(rows)==1;return rows[0]

def verify(state,native,action,marker):
    operation=marker['operation_id'];bundle=f.load(OUT/(action+'-bundle.json'));before=f.load(j.LOCAL/('core13-feature-'+action+'-before.json'))
    native=NativeFeatureExecutor(native.store,native.target_path,native.catalog_root,native.validator)
    assert native.store.status(operation)['state']=='completed'
    after=snapshot(state,'core13-feature-'+action+'-after');target=bundle['operation_lock']['targets'][0]
    stage=native.store.root/'stages'/operation;checkpoint=native.store.root/'checkpoints'/operation
    fence=f.load(stage/'dispatch-fence/fence.json')['result'];ready=f.load(stage/'dispatch-ready.json');enabled=f.load(stage/'dispatch-enable/enable.json')['result']
    assert enabled['after']['control']['generation']==marker['before_dispatch']+3
    assert fence['after']['control']['generation']==marker['before_dispatch']+1 and ready['control']['generation']==marker['before_dispatch']+2
    expected_availability='suspended' if action=='suspend' else 'enabled'
    ids={r['public_id']:r['id'] for r in before['mp_workspace']};workspace_id=ids[target['workspace_id']]
    installation_id=next(r['id'] for r in before['mp_plugin_installation'] if r['public_id']==target['installation_id'])
    cutoff=datetime.fromisoformat(bundle['plan']['created_at'].replace('Z','+00:00'));changed_jobs=0
    for table in TABLES:
        expected=copy.deepcopy(before[table]);actual=copy.deepcopy(after[table]);assert len(expected)==len(actual)
        if table=='mp_workspace_plugin':
            old=next(r for r in expected if r['workspace_id']==workspace_id and r['installation_id']==installation_id)
            new=next(r for r in actual if r['id']==old['id'])
            old['availability']=expected_availability
            stamp=datetime.fromisoformat(new['write_date']).replace(tzinfo=timezone.utc);assert cutoff<=stamp<=datetime.now(timezone.utc)
            old['write_date']=new['write_date']
        elif table=='mp_workspace':next(r for r in expected if r['id']==workspace_id)['policy_generation']+=1
        elif table=='mp_job':
            byid={r['public_id']:r for r in actual}
            for old in expected:
                new=byid[old['public_id']];changed={k for k in old if old[k]!=new[k]}
                assert changed<={'claim_generation','dispatch_generation'}
                if changed:
                    assert new['claim_generation']==old['claim_generation']+1 and new['dispatch_generation']==ready['control']['generation'];changed_jobs+=1
                    old.update(claim_generation=new['claim_generation'],dispatch_generation=new['dispatch_generation'])
        assert expected==actual,table+' changed beyond exact native feature effects'
    current=native.observer.state(native.observer.read(),Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
    assert current['release_lock']==bundle['operation_lock']['release'] and native.config['generation']==11
    features=next(i for i in current['installations'] if i['installation_id']==target['installation_id'] and i['workspace_id']==target['workspace_id'])
    assert features['state']=='installed' and features['feature_state']==expected_availability
    assert f.load(stage/'native-skipped.json')['reason'].startswith('Reviewed native feature availability only')
    assert f.load(stage/'feature.log')==dict(feature_metadata_published=True,operation_id=operation,native_maintenance=False,runtime_control=False)
    audit=json.loads(f.sql(state,'core13-feature-'+action+'-audit',"BEGIN READ ONLY; SELECT jsonb_agg(jsonb_build_object('action',action,'workspace',workspace_public_id,'plugin',plugin_id,'metadata',metadata)) FROM mp_audit_event WHERE request_id='"+operation+"'; ROLLBACK;"))
    assert audit==[dict(action='operator.feature_'+action,workspace=target['workspace_id'],plugin='org.example.notes',metadata=dict(plan_hash=bundle['plan_hash']))]
    views=native_probe(state,native,'core13-feature-'+action+'-native-views',expected_availability)
    files=json.loads(f.command('core13-feature-'+action+'-files',['docker','exec',native.observer._container('app'),'/venv/bin/python','-c',FILE_OBSERVATION,state['active_db']]))
    retained={};prefix='filestore/'+state['active_db']+'/'
    with tarfile.open(checkpoint/'filestore.tar.gz','r:gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith(prefix):retained[member.name[len(prefix):]]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
    assert retained and all(files.get(p)==digest for p,digest in retained.items())
    assert f.load(native.target_path)['published_release']==f.load(stage/'configuration.json')['published_release']
    report=dict(result='passed_actual_checkpointed_native_feature',action=action,operation_id=operation,plan_hash=bundle['plan_hash'],
        image=native.config['image_id'],configuration_generation=11,release_unchanged=True,dispatch_generation=enabled['after']['control']['generation'],
        native_views=views,native_addon_still_installed=True,no_native_install_unload_or_migration=True,
        table_rows_preserved_except_exact_target_feature_policy_and_job_epochs=True,counts={t:len(r) for t,r in after.items()},
        jobs_epoch_updated=changed_jobs,old_checkpoint_files_preserved=len(retained),exact_single_feature_audit=True,
        limits=['Actual native feature path with terminal queue history; no new pending/remote jobs in this cycle.',
            'Installed native list/form model methods probed; no new browser rendering or external metadata/SVC proof.'])
    f.save(action+'-qualification.json',report);marker['state']='verified';f.write(j.LOCAL/('core13-feature-'+action+'.json'),marker)
    f.phase(state,'core13_feature_'+action+'_verified');f.guard(state)
    print(json.dumps(dict(result=report['result'],action=action,dispatch_generation=report['dispatch_generation'])))

def run(action):
    state,native=context();marker_path=j.LOCAL/('core13-feature-'+action+'.json');assert not marker_path.exists()
    assert native.config['generation']==11 and native.observer.read()['runtime']['platform_version']=='0.1.13'
    if action=='enable':assert f.load(j.LOCAL/'core13-feature-suspend.json')['state']=='verified'
    catalog=Catalog(native.catalog_root,native.validator,readonly=True);observation=native.observer.read();document=native.observer.state(observation,catalog.snapshot())
    scope=f.load(j.LOCAL/'fixtures.json')['workspaces']['C']['public_id']
    row=next(i for i in document['state']['installations'] if i['plugin_id']=='org.example.notes' and i['workspace_id']==scope)
    assert row['feature_state']==('enabled' if action=='suspend' else 'suspended')
    target={k:row[k] for k in ['installation_id','site_id','workspace_id','plugin_id']};target['action']=action
    bundle=prepare_current_feature(document,observation['sites'],catalog.snapshot(),targets=[target],operation_type=action,
        operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    assert bundle['plan']['backup']['required'] and not bundle['plan']['permission_changes'] and bundle['display']['restart_required']
    native._runtime_preflight(bundle)
    f.save(action+'-bundle.json',bundle);before=snapshot(state,'core13-feature-'+action+'-before');f.write(j.LOCAL/('core13-feature-'+action+'-before.json'),before)
    dispatch=DispatchMaintenance(native).inspect();DispatchMaintenance.require_native(dispatch)
    marker=dict(state='prepared',operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash'],before_dispatch=dispatch['control']['generation'])
    f.write(marker_path,marker)
    prefix=[sys.executable,'-X','utf8','tools/modular.py','--config',str(j.LOCAL/'operator/trust.json')]
    options=['--deployment-config',str(native.target_path),'--catalog',str(native.catalog_root)];ops=prefix+['operations','--store',str(native.store.root)]
    f.command('core13-feature-'+action+'-register',ops+['register','--bundle',str(OUT/(action+'-bundle.json'))]+options)
    f.save(action+'-review.json',native.store.review(marker['operation_id'],native._validate()))
    f.command('core13-feature-'+action+'-approve',ops+['approve',marker['operation_id'],'--plan-hash',marker['plan_hash'],'--noninteractive','--ack-trust']+options)
    marker['state']='applying';f.write(marker_path,marker);f.phase(state,'core13_feature_'+action+'_applying')
    result=json.loads(f.command('core13-feature-'+action+'-apply',prefix+['plugin','apply',marker['operation_id'],'--store',str(native.store.root)]+options,timeout=600))
    assert result['state']=='completed';f.save(action+'-completed.json',result)
    marker['state']='completed_needs_verification';f.write(marker_path,marker)
    verify(state,native,action,marker)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['suspend','enable']);args=parser.parse_args();run(args.action)
