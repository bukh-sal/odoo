"""Bind UI05/UI10 browser/source evidence to the current Canvas/data release."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from modular import configuration
from qualify_native_upgrade import sql
from qualify_release_reader_rollout import notes_snapshot,files
import r1,r1_probe
r1.r0.LOCAL=ROOT/'.local/g5'


def main():
    output=ROOT/'docs/evidence/G5/20261028T155500Z-canvas-reuse-browser'
    if (output/'canvas-requalification.json').exists():raise ValueError('Canvas qualification already recorded; never overwrite')
    local=ROOT/'.local/g5';operator=ROOT/'.local/operator';config=json.loads((operator/'targets/g5.json').read_text())
    assert config['project']=='mp-r0-r1g5fd0445d406d6' and config['generation']==16
    install=json.loads((local/'canvas-reuse-install.json').read_text());assert install['state']=='completed'
    baseline=json.loads((ROOT/install['evidence']/'preservation-before.json').read_text())
    catalog=Catalog(operator/'catalog',configuration(operator/'trust.json'),readonly=True).snapshot()
    observer=DockerObserver(config);observed=observer.read();state=observer.state(observed,catalog)['state']
    assert notes_snapshot(observer)==baseline['notes'] and len(baseline['notes'])==4
    current_files=files(observer);assert all(current_files.get(name)==digest for name,digest in baseline['filestore'].items())
    seed=json.loads((local/'canvas-reuse-board.json').read_text());assert seed['state']=='created'
    board=json.loads(sql(observer,"SELECT jsonb_build_object('id',b.public_id,'name',b.name,'revision',b.revision,'cards',b.cards,'workspace_id',w.public_id) FROM mp_example_canvas_board b JOIN mp_workspace w ON w.id=b.workspace_id;"))
    assert board['id']==seed['board']['public_id'] and board['name']==seed['name'] and board['cards']==seed['board']['cards']
    assert board['revision']==2 and board['workspace_id']==seed['workspace_id']
    assert sql(observer,'SELECT count(*) FROM mp_example_canvas_board;').strip()==b'1'
    browser=json.loads((output/'browser-observations.json').read_text());draft=json.loads((output/'recovered-canvas-draft.json').read_text())
    assert all(row['canvasRegionsAway']==0 and row['canvasRegionsMounted']==1 for row in browser['mount_cycles'])
    assert len(browser['mount_cycles'])==3 and browser['one_keyboard_save_revision']==2
    for key in ['pending_native_confirmation_cancelled_on_expiry','expired_page_removed','different_principal_download_denied',
            'recovery_control_removed_on_principal_change','alice_session_restored']:assert browser[key]
    assert browser['final_dom']=={'name':seed['name'],'card':seed['board']['cards'][0]['text'],'canvasRegions':1,'dialogs':0}
    assert draft['board_id']==board['id'] and draft['expected_revision']==2
    assert draft['name']=='UI10 unsaved Canvas recovery draft' and draft['cards'][0]['text']=='UI10 unsaved card must survive session expiry'
    image_files=observed['runtime']['inventory']['files'];paths=[]
    for folder,names in [('mp_shell',['host.js','native_interactions.js','host.css']),('mp_example_canvas',['page.js','adapter.js'])]:
        for name in names:
            path=ROOT/'platform_addons'/folder/'static/src'/name;paths.append(path)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==image_files['addons/'+folder+'/static/src/'+name]
    fixture=json.loads((local/'fixtures.json').read_text());local_state=json.loads((local/'state.json').read_text());alice=r1_probe.Client(local_state,fixture,'alice')
    status,context=alice.request('/api/v1/context?plugin_id=org.example.canvas',workspace='A');assert status==200
    bindings={row['alias']:row for row in context['data']['bindings']};assert bindings['documents']['api_version']=='2.0' and bindings['boards']['api_version']=='1.0'
    binding=bindings['boards'];status,result=alice.request('/api/v1/services/'+binding['service_id']+'/get',
        {'api_version':binding['api_version'],'request_id':'canvas-requalification-read','input':{'board_id':board['id']}},'A',
        {'X-CSRFToken':alice.csrf,'X-MP-Binding':binding['binding_id'],'X-MP-Consumer':context['data']['context']['installation_id']})
    assert status==200 and result['data']=={key:value for key,value in board.items() if key!='workspace_id'}
    assert observer.state(observer.read(),catalog)['state']==state
    paths+=[Path(__file__),ROOT/'tests/test_canvas_lifecycle.mjs',ROOT/'tools/qualify_ui_reuse_source.py']
    report={'result':'passed_UI05_UI10_requalification','utc':datetime.now(timezone.utc).isoformat(),'image_id':config['image_id'],
        'generation':config['generation'],'worker_id':config['worker_id'],'database':config['sites'][0]['database'],
        'canvas_install_operation':install['operation_id'],'state_digest':data_digest(state),'board':board,
        'source_checks':'docs/evidence/G5/20261028T160500Z-canvas-lifecycle-source/ui-reuse-source.json',
        'checks':['5 real-page Node lifecycle tests instrument document EventTargets/theme subscriptions, late initial/save responses and JSON snapshot',
            '3 real browser mount/dispose cycles; zero old Canvas DOM, one current page; one CtrlS increments revision once',
            'Native unsaved confirmation/Escape; expiry cancels pending confirmation/removes page; exact unsaved draft downloaded locally',
            'Different authenticated principal cannot download old draft; retained snapshot/control cleared',
            'Alice session restored; saved board remains revision2/original name/cards; no automatic save of unsaved edits',
            'Original4Notes, prior asset bytes and current deployment identity preserved; real boards1.0/documents2.0 binding/get succeeds'],
        'source_sha256':{path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        'artifacts_sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in output.iterdir() if path.is_file()},
        'limits':['Reference board was explicitly provisioned through Alice scoped native API; fresh Canvas initial-board creation remains G5 work.',
            'No native action/view pilot, client release epoch/UI07, full UI09 or G5 exit claimed.']}
    (output/'canvas-requalification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'generation':config['generation'],'original_notes_preserved':4,'board_revision':board['revision']}))


if __name__=='__main__':main()
