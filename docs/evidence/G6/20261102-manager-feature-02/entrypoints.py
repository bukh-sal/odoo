"""Real original-user HTTP availability and native-view checks around suspension."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import OUT,PRIVATE,MARKER,context,f,base,j
import r1_probe
from modular_platform.contracts import ERROR_STATUS,validate
r1_probe.r1.r0.LOCAL=j.LOCAL

def run(expected):
    state,native=context();cycle=f.load(MARKER)
    assert cycle['suspend']['state']==('awaiting_manager_request' if expected=='enabled' else 'preservation_verified')
    before=base.snapshot(state,'manager02-entrypoints-'+expected+'-before');worker=base.worker(native,'manager02-entrypoints-'+expected+'-worker-before')
    fixture=f.load(j.LOCAL/'fixtures.json');alice=r1_probe.Client(state,fixture,'alice')
    status,response=alice.request('/api/v1/context?plugin_id=org.example.document_stats',workspace='C')
    if expected=='enabled':
        assert status==200 and response['data']['context']['plugin_id']=='org.example.document_stats'
        assert response['data']['context']['workspace_id']==cycle['scope']['workspace_id']
        f.save('enabled-context-before.json',dict(policy_generation=response['data']['context']['policy_generation'],provider_context_available=True))
    else:
        assert status==ERROR_STATUS['PLUGIN_SUSPENDED'] and response['error']['code']=='PLUGIN_SUSPENDED'
    views={}
    for name in ['A','B','C']:
        value=alice.native('get_views',args=[[[False,'list'],[False,'form']]],kwargs={'options':{}},workspace=name)
        assert set(value['views'])=={'list','form'} and '<list' in value['views']['list']['arch'] and '<form' in value['views']['form']['arch']
        views[name]='native_list_form_available'
    if expected=='suspended':
        status,notes=alice.request('/api/v1/context?plugin_id=org.example.notes',workspace='C')
        assert status==200 and notes['data']['context']['policy_generation']==f.load(OUT/'enabled-context-before.json')['policy_generation']+1
    operator=r1_probe.Client(state,fixture,'operator')
    status,response=operator.request('/api/v1/operations/installed');assert status==200;validate('manager-view',response['data'])
    row=next(r for r in response['data']['items'] if r['plugin_id']=='org.example.document_stats')
    assert row['database_state']=='installed' and row['native_version'] is None and row['health']['state']=='healthy'
    assert len(row['features'])==1 and row['features'][0]['availability']==expected
    assert base.snapshot(state,'manager02-entrypoints-'+expected+'-after')==before
    assert base.worker(native,'manager02-entrypoints-'+expected+'-worker-after')==worker==f.load(PRIVATE/'worker-before.json')
    f.save('entrypoints-'+expected+'.json',dict(result='passed_actual_http_'+expected+'_provider',provider_context_status=status if expected=='enabled' else ERROR_STATUS['PLUGIN_SUSPENDED'],
        provider_context_available=expected=='enabled',native_views=views,manager_reports_process_health_separate_from_feature_availability=True,
        all17tables_and_independent_worker_exact=True,original_actor_uid=fixture['users']['alice']['id'],browser_rendering_tested=False,
        limits=['Host context/native view definitions only; no native connector/remote computation installed.']))
    f.guard(state);print('Actual HTTP provider '+expected+' gates and independent healthy process verified; native A/B/C list/form and data intact')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('state',choices=['enabled','suspended']);args=p.parse_args();run(args.state)
