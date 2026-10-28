"""Read-only post-browser reconciliation of the exact retained clone."""
import argparse
from datetime import datetime,timezone
import json
import hashlib
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.plans import data_digest
from modular import configuration
from qualify_client_release_clone import command,BUSINESS_SQL
import r1,r1_probe


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--clone-record',required=True,type=Path);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    marker=args.clone_record.resolve();assert marker.is_relative_to(ROOT/'.local/g5/client-release-clones')
    clone=json.loads(marker.read_text(encoding='utf-8'));assert clone['state']=='browser_qualifying' and clone['experimental_not_approved_release']
    database=clone['database'];assert re.fullmatch(r'mp_disposable_r0_r1_client_[0-9a-f]{16}',database)
    output=args.output.resolve();assert output.is_relative_to(ROOT/'docs/evidence/G5') and not output.exists()
    config=json.loads((ROOT/'.local/operator/targets/g5.json').read_text(encoding='utf-8'))
    observer=DockerObserver(config);catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot()
    before=observer.state(observer.read(),catalog)['state'];assert data_digest(before)==clone['source_state_digest']
    db=observer._container('db')
    def sql(statement,name=database):return command(['docker','exec','-i',db,'psql','-X','-qAt','-U','postgres','-v','ON_ERROR_STOP=1','-d',name],input=statement.encode())
    business=json.loads(sql(BUSINESS_SQL));source_business=json.loads(sql(BUSINESS_SQL,clone['source_database']))
    assert business==source_business and data_digest(business)==clone['business_digest']
    assert len(business['notes'])==4 and len(business['boards'])==1 and business['boards'][0]['revision']==2
    assert all(row['public_id']!='aeddb23e-cdd0-497b-b916-e85929fa16b8' for row in business['notes'])
    fixture=json.loads((ROOT/'.local/g5/fixtures.json').read_text(encoding='utf-8'));fixture['bindings']={}
    for key,space in fixture['workspaces'].items():
        consumer=next(item for item in before['installations'] if item['plugin_id']=='org.example.notes' and item['workspace_id']==space['public_id'])
        fixture['bindings'][key]=next(item for item in before['bindings'] if item['consumer_installation_id']==consumer['installation_id'] and item['workspace_id']==space['public_id'] and item['alias']=='documents')
    r1.r0.LOCAL=ROOT/'.local/g5';client=r1_probe.Client({'active_db':database,'port':clone['port']},fixture)
    status,context=client.request('/api/v1/context?plugin_id=org.example.notes',workspace='A');assert status==200
    current=context['data']['release'];assert current['generation']==clone['generation']==18
    epoch=json.loads((ROOT/'docs/evidence/G5/20261028-client-release-epoch18/experimental-epoch.json').read_text(encoding='utf-8'))
    old={key:value for key,value in current.items() if key!='token'};old.update(generation=17,release_digest=epoch['previous']['mp.release_digest'])
    old_token=data_digest(old);assert old_token!=current['token']
    row=next(item for item in business['notes'] if item['workspace_id']==next(board['workspace_id'] for board in business['boards']))
    client.call('get',{'note_id':row['public_id']})
    result=client.call('get',{'note_id':row['public_id']},headers={'X-MP-Client-Release':old_token},expect=409,code='CONFLICT')
    assert result['error']['details']=={'field':'client_release','outcome':'not_started'}
    client.native('read',[[row['id']],['public_id','title']])
    files_script="import hashlib,json,pathlib,sys;p=pathlib.Path('/var/lib/modular/filestore')/sys.argv[1];print(json.dumps({f.relative_to(p).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()}))"
    source_files=json.loads(command(['docker','exec',observer._container('app'),'/venv/bin/python','-c',files_script,clone['source_database']]))
    clone_files=json.loads(command(['docker','exec',clone['app'],'/venv/bin/python','-c',files_script,database]))
    assert source_files and all(clone_files.get(name)==digest for name,digest in source_files.items())
    assert observer.state(observer.read(),catalog)['state']==before
    browser=ROOT/clone['evidence']/'browser'
    native=json.loads((browser/'recovered-native-draft.json').read_text(encoding='utf-8'))
    canvas=json.loads((browser/'recovered-canvas-draft.json').read_text(encoding='utf-8'))
    native_expired=json.loads((browser/'recovered-native-expired-session-draft.json').read_text(encoding='utf-8'))
    canvas_expired=json.loads((browser/'recovered-expired-session-draft.json').read_text(encoding='utf-8'))
    assert native=={'title':'Unsaved native draft across release 18 d44f','body':'Native draft body across release 18.'}
    assert canvas['name']=='Unsaved Canvas draft across release 18 d44f' and canvas['expected_revision']==2 and len(canvas['cards'])==2
    assert native_expired=={'title':'Native session-expiry draft d44f','body':'Unsaved native body preserved after session expiry.'}
    assert canvas_expired['name']=='Session-expiry draft d44f' and canvas_expired['expected_revision']==2
    assert json.loads((browser/'mount-cycles.json').read_text(encoding='utf-8'))==[{'cycle':n,'mounted':1,'afterDisposal':0} for n in [1,2,3]]
    output.mkdir(parents=True)
    report={'result':'passed_postbrowser_subset','utc':datetime.now(timezone.utc).isoformat(),'clone_database':database,'image_id':clone['image_id'],
        'clone_generation':18,'source_generation':config['generation'],'source_state_digest':data_digest(before),'business_digest':data_digest(business),
        'original_notes':4,'boards':1,'board_revision':2,'named_crud_fixture_deleted_only_in_clone':True,'unsaved_drafts_not_saved':True,
        'old_epoch_token_still_denied':True,'new_epoch_current_pin_positive':True,'source_filestore_files_preserved':len(source_files),'clone_filestore_files':len(clone_files),
        'drafts_exact':True,'three_mount_cycles':True,'operated_source_unchanged':True,
        'source_sha256':{Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'limits':['Audit/session/idempotency and generated native assets changed in the clone; no full unchanged-database claim.',
            'Experimental metadata epoch and direct clone maintenance do not qualify independent approved deployment/fault/recovery or real changed-asset client activation.']}
    (output/'postbrowser.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    clone.update(state='browser_qualified_subset',utc=report['utc'],postbrowser_evidence=output.relative_to(ROOT).as_posix())
    clone.pop('interrupted_phase',None);clone.pop('error_type',None)
    marker.write_text(json.dumps(clone,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'result':report['result'],'original_notes':4,'board_revision':2,'source_unchanged':True}))


if __name__=='__main__':main()
