"""Two explicit scoped records for the approved 2.2-to2.3 migration proof."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-manager-upgrade-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from qualify_manager_upgrade_operation import snapshot
import r1,r1_probe


def main():
    marker=LOCAL/'record-seed.json';assert not marker.exists(),'Inspect recorded keys/outcomes; never create fresh retry identities'
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));config=json.loads((LOCAL/'operator/target.json').read_text(encoding='utf-8'))
    assert config['generation']==2 and state['phase']=='notes_installed' and state['project']=='mp-r0-r1mgr84459f617ab0'
    main_hash=hashlib.sha256((ROOT/'.local/operator/targets/g5.json').read_bytes()).hexdigest();assert main_hash==state['main_target_sha256']
    observer=DockerObserver(config);validator=configuration(ROOT/'.local/operator/trust.json');catalog=Catalog(ROOT/'.local/operator/catalog',validator,readonly=True)
    before=snapshot(observer);assert before['notes']==[] and before['native_version']=='19.0.0.2.2' and before['migration_pre'] is None and before['migration_post'] is None
    document=observer.state(observer.read(),catalog.snapshot())['state'];fixture=json.loads((LOCAL/'fixtures.json').read_text(encoding='utf-8'));workspace=fixture['workspaces']['A']['public_id']
    binding=next(row for row in document['bindings'] if row['workspace_id']==workspace and row['alias']=='documents' and row['contract_major']==1)
    fixture['database']=state['active_db'];fixture['bindings']={'A':binding};(LOCAL/'fixtures.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf-8')
    record={'state':'nominated','workspace_id':workspace,'keys':[str(uuid4()) for _ in range(3)],'outcomes':[],'created_at':datetime.now(timezone.utc).isoformat()}
    def phase(value):
        record['state']=value;marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    phase('nominated');r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'alice')
    for index in range(2):
        phase('creating_record_'+str(index+1));result=client.call('create',{'title':'Manager upgrade fixture '+str(index+1),'body':'Explicit retained native migration record.'},key=record['keys'][index]);record['outcomes'].append(result);phase('record_'+str(index+1)+'_created')
    phase('updating_second_revision');updated=client.call('update',{'note_id':record['outcomes'][1]['id'],'expected_revision':1,'title':'Manager upgrade fixture revision two'},key=record['keys'][2]);assert updated['revision']==2
    after=snapshot(observer);assert len(after['notes'])==2 and sorted(row['revision'] for row in after['notes'])==[1,2]
    assert all(after[key]==before[key] for key in ['features','bindings','grants','native_state','native_version','positive_constraint','migration_pre','migration_post'])
    record.update(state='seeded_verified',notes=after['notes']);marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (OUTPUT/'retained-records-before-upgrade.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    assert hashlib.sha256((ROOT/'.local/operator/targets/g5.json').read_bytes()).hexdigest()==main_hash
    print(json.dumps({'result':'seeded_two_scoped_records','workspace_id':workspace,'revisions':[1,2],'main_target_unchanged':True}))


if __name__=='__main__':main()
