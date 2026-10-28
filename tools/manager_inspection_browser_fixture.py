"""Temporary untrusted catalog mirror probes for G5-X02; never real artifacts."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];LOCAL=ROOT/'.local/g5-manager-upgrade'
OUTPUT=ROOT/'docs/evidence/G5/20261029-manager-inspection-http-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.deployment import DockerObserver
from qualify_manager_upgrade_operation import sql,snapshot

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['setup','restore']);args=parser.parse_args()
    state=json.loads((LOCAL/'state.json').read_text(encoding='utf-8'));config=json.loads((LOCAL/'operator/target.json').read_text(encoding='utf-8'))
    assert state['project']==config['project']=='mp-r0-r1mgr84459f617ab0' and config['generation']==4
    assert json.loads((LOCAL/'inspection-http.json').read_text(encoding='utf-8'))['state']=='completed_verified'
    assert hashlib.sha256((ROOT/'.local/operator/targets/g5.json').read_bytes()).hexdigest()==state['main_target_sha256']
    reader=DockerObserver(config);marker=LOCAL/'inspection-browser-fixture.json';backup=LOCAL/'inspection-profile-before.json'
    query="SELECT payload FROM mp_operation_profile WHERE site_public_id='365532d7-921e-43bc-8d49-b037a7183308';"
    current=json.loads(sql(reader,query));business=snapshot(reader)
    def publish(value):
        encoded=base64.b64encode(json.dumps(value).encode()).decode()
        count=sql(reader,"WITH changed AS (UPDATE mp_operation_profile SET payload=convert_from(decode('"+encoded+"','base64'),'UTF8')::jsonb WHERE site_public_id='365532d7-921e-43bc-8d49-b037a7183308' RETURNING id) SELECT count(*) FROM changed;")
        assert count.strip()==b'1' and json.loads(sql(reader,query))==value
    if args.action=='setup':
        assert not marker.exists() and not backup.exists()
        backup.write_text(json.dumps({'profile':current,'business':business},indent=2)+'\n',encoding='utf-8')
        profile=copy.deepcopy(current);old=next(d for d in profile['catalog'] if d['plugin_id']=='org.example.notes' and d['version']=='0.2.2')
        old['manifest']['plugin']['publisher']='<b data-mp-g5-escape="publisher">Fixture publisher</b>'
        template=copy.deepcopy(old)
        for n in range(15):
            item=copy.deepcopy(template);ident='org.test.catalog'+str(n).zfill(2)
            item.update(plugin_id=ident,version='1.0.0',digest='sha256:'+hashlib.sha256(('metadata-page-'+str(n)).encode()).hexdigest())
            item['manifest']['plugin'].update(id=ident,version='1.0.0',name='Catalog fixture '+str(n).zfill(2),publisher='Metadata-only fixture')
            profile['catalog'].append(item)
        uploads=LOCAL/'uploads';uploads.mkdir(exist_ok=True)
        for name,raw in [('not-curated.mplug',b'Unapproved synthetic reference upload'),('invalid-mirrored.mplug',b'Not a ZIP archive')]:
            with (uploads/name).open('xb') as stream:stream.write(raw)
        invalid=copy.deepcopy(template);invalid.update(plugin_id='org.test.invalid',version='1.0.0',digest='sha256:'+hashlib.sha256(b'Not a ZIP archive').hexdigest())
        invalid['manifest']['plugin'].update(id='org.test.invalid',version='1.0.0',name='Invalid mirror fixture',publisher='Metadata-only fixture');profile['catalog'].append(invalid)
        record={'state':'publishing','catalog_items':len(profile['catalog']),'purpose':'Untrusted mirror-only pagination, inert markup escaping and invalid upload branch; no real catalog/trust/artifact/approval changes.'}
        marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');publish(profile);assert snapshot(reader)==business
        record.update(state='active_needs_restore',utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
        (OUTPUT/'browser-fixture.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');print(json.dumps(record));return
    record=json.loads(marker.read_text(encoding='utf-8'));assert record['state']=='active_needs_restore'
    original=json.loads(backup.read_text(encoding='utf-8'));publish(original['profile']);assert snapshot(reader)==original['business']
    record.update(state='restored_verified',utc=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    (OUTPUT/'browser-fixture-restored.json').write_text(json.dumps(record|{'profile_exact':True,'business_features_bindings_grants_exact':True},indent=2)+'\n',encoding='utf-8');print(json.dumps(record))

if __name__=='__main__':main()
