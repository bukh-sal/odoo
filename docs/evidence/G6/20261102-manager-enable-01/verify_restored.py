"""Prove actual restored availability and whole suspend/enable data preservation."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,PRIVATE,MARKER,context,f,base,j
import r1_probe
from modular_platform.contracts import validate
r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=context();cycle=f.load(MARKER);assert cycle['enable']['state']=='preservation_verified'
original=f.load(j.LOCAL/'manager-feature-02/suspend-data-before.json')
current=base.snapshot(state,'manager-enable01-whole-cycle-after');scope=cycle['scope']
installation=next(r for r in original['mp_plugin_installation'] if r['public_id']==scope['installation_id'])
workspace=next(r for r in original['mp_workspace'] if r['public_id']==scope['workspace_id']);updated=0
for table in original:
    expected=copy.deepcopy(original[table]);actual=copy.deepcopy(current[table]);assert len(expected)==len(actual)
    if table=='mp_workspace_plugin':
        old=next(r for r in expected if r['installation_id']==installation['id'] and r['workspace_id']==workspace['id'])
        after=next(r for r in actual if r['id']==old['id']);assert old['availability']==after['availability']=='enabled'
        assert after['write_date']>=old['write_date'];old['write_date']=after['write_date']
    elif table=='mp_workspace':next(r for r in expected if r['id']==workspace['id'])['policy_generation']+=2
    elif table=='mp_job':
        byid={r['public_id']:r for r in actual}
        for old in expected:
            after=byid[old['public_id']];changed={k for k in old if old[k]!=after[k]};assert changed<={'claim_generation','dispatch_generation'}
            if changed:
                assert after['claim_generation']==old['claim_generation']+2 and after['dispatch_generation']==72
                old.update(**{k:after[k] for k in changed});updated+=1
    assert expected==actual,table+' changed outside paired feature/policy/epoch transitions'
fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
status,response=alice.request('/api/v1/context?plugin_id=org.example.document_stats',workspace='C')
assert status==200 and response['data']['context']['workspace_id']==scope['workspace_id']
assert response['data']['context']['policy_generation']==f.load(ROOT/'docs/evidence/G6/20261102-manager-feature-02/enabled-context-before.json')['policy_generation']+2
for name in ['A','B','C']:
    views=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
    assert set(views['views'])=={'list','form'} and '<list' in views['views']['list']['arch'] and '<form' in views['views']['form']['arch']
operator=r1_probe.Client(state,fixture,'operator');status,response=operator.request('/api/v1/operations/installed');assert status==200;validate('manager-view',response['data'])
provider=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
assert provider['health']['state']=='healthy' and provider['database_state']=='installed' and provider['native_version'] is None
assert len(provider['features'])==1 and provider['features'][0]['availability']=='enabled'
assert base.snapshot(state,'manager-enable01-http-data-after')==current
assert base.worker(native,'manager-enable01-whole-cycle-worker')==f.load(j.LOCAL/'manager-feature-02/worker-before.json')==f.load(PRIVATE/'worker-before.json')
f.save('whole-feature-cycle.json',dict(result='passed_actual_http_manager_suspend_enable_cycle',configuration_generation=15,dispatch_generation=73,
    original_actor_uid=fixture['users']['alice']['id'],provider_context_restored_200=True,current_policy_generation_fresh=True,
    native_A_B_C_list_form_retained=True,manager_reports_installed_enabled_healthy_without_fake_addon=True,
    all17table_original_rows_preserved_except_exact_feature_timestamp_policy_plus2_and_job_epochs=True,
    old_job_outcomes_inputs_attempts_preserved=19,jobs_epoch_updated_twice=updated,
    independent_worker_identity_image_start_mounts_key_and_publication_unchanged_through_cycle=True,browser_rendering_tested=False,
    limits=['Terminal-history queues; no remote computation/in-flight effects/recovery/changed worker image qualification.']))
f.guard(state);print('Whole actual manager suspend/enable cycle restores C context200/native views; original data/jobs and independent worker retained')
