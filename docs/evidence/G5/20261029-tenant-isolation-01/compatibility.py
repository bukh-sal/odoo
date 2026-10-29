"""Actual older native DB under current shared runtime: proposal/start refusal."""
import configparser
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import runpy
import secrets
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-tenant'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.resolution import PlanningError
from modular_platform.operator_os import OperatorError
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');assert state['phase']=='HTTP_isolation_verified' and 'c' not in state['cases'];dest=OUTPUT/'compatibility-qualification.json';assert not dest.exists()
    main_config=load(ROOT/'.local/operator/targets/g5.json');life=load(ROOT/'.local/g5-lifecycle/operator/target.json');life_state=load(ROOT/'.local/g5-lifecycle/state.json');source=DockerObserver(main_config);db=state['db_container'];database=state['active_db'][:-1]+'c';volume=state['project']+'_probe_c'
    def save(phase):state.update(phase=phase,utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    def command(args,*,input=None,timeout=180):
        r=subprocess.run(args,input=input,capture_output=True,timeout=timeout)
        if r.returncode:
            (LOCAL/'compatibility.stderr').write_bytes(r.stderr);raise RuntimeError('Inspect exact compatibility marker/resources; never reset/recreate')
        return r.stdout
    before=dict(business=json.loads(sql(source,BUSINESS_SQL)),schema=json.loads(sql(source,SCHEMA)),configuration=main_config)
    (OUTPUT/'setup/source-c.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf8')
    state['cases']['c']=dict(database=database,volume=volume,source_database=main_config['sites'][0]['database'],site_id=main_config['sites'][0]['site_id'],labels_installed=True,source_image=main_config['image_id'],source_inventory=main_config['published_release']['core_inventory_digest']);state['databases'].append(database);save('copying_incompatible_c')
    archive=command(['docker','exec',source._container('db'),'pg_dump','-U','postgres','--no-owner','-Fc',main_config['sites'][0]['database']]);(LOCAL/'source-c.dump').write_bytes(archive)
    command(['docker','exec',db,'createdb','-U','postgres','-T','template0','-O','modular',database]);command(['docker','exec','-i',db,'pg_restore','-U','postgres','--no-owner','--role=modular','--exit-on-error','-d',database],input=archive)
    own_config=dict(life,project=state['project'],sites=[dict(database=database,site_id=state['cases']['c']['site_id'])]);own_config.pop('worker_id',None);own_config.pop('published_release',None);reader=DockerObserver(own_config)
    assert json.loads(sql(reader,BUSINESS_SQL))==before['business'] and json.loads(sql(reader,SCHEMA))==before['schema']
    sql(reader,"BEGIN; UPDATE ir_config_parameter SET value='"+str(uuid4())+"' WHERE key='mp.deployment_id'; UPDATE ir_config_parameter SET value='"+secrets.token_hex(32)+"' WHERE key='database.secret'; UPDATE mp_service_credential SET state='revoked'; COMMIT;")
    raw=command(['docker','exec',main_config['worker_id'],'/venv/bin/python','-c',"from pathlib import Path;print(Path('/run/secrets/odoo_config').read_text(),end='')"]);cfg=configparser.ConfigParser();cfg.read_string(raw.decode());cfg['options'].update(db_name=database,dbfilter='^'+database+'$',db_password=(LOCAL/'app-db-password').read_text(encoding='utf8').strip(),admin_passwd=(LOCAL/'database-master-password').read_text(encoding='utf8').strip(),workers='0',max_cron_threads='0');stream=io.StringIO();cfg.write(stream)
    command(['docker','volume','create','--label','com.modular.qualification=G5-tenant-isolation',volume]);seed=runpy.run_path(str(OUTPUT/'setup.py'))['SEED']
    command(['docker','run','--rm','-i','--network','none','--read-only','--user','0:0','--cap-drop','ALL','--cap-add','CHOWN','--mount','type=volume,source='+main_config['project']+'_filestore,target=/source,readonly','--mount','type=volume,source='+volume+',target=/target','--entrypoint','/venv/bin/python',state['image_id'],'-c',seed],input=json.dumps(dict(config=stream.getvalue(),source_database=main_config['sites'][0]['database'],database=database)).encode())
    schema=json.loads(sql(reader,SCHEMA));business=json.loads(sql(reader,BUSINESS_SQL));assert schema==before['schema']
    for key,value in [('c-schema',schema),('c-business',business)]: (OUTPUT/'setup'/(key+'.json')).write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
    native=schema['native'];assert ['mp_example_notes_labels','installed','19.0.0.2.1'] in native
    assert ['mp_example_notes_labels','installed','19.0.0.2.2'] in load(OUTPUT/'setup/a-schema.json')['native']
    catalog=Catalog(ROOT/life_state['operator_catalog'],configuration(ROOT/life_state['operator_trust_config']),readonly=True).snapshot()
    shared=dict(own_config,sites=[dict(database=r['database'],site_id=r['site_id']) for r in state['cases'].values()]);observer=DockerObserver(shared)
    save('observing_complete_shared_runtime');observed=observer.read(quiesced=True,missing_worker=True)
    assert len(observed['sites'])==3 and observer.removal_site_inventory(observed)['complete']
    omitted=dict(shared,sites=shared['sites'][:1]);partial=DockerObserver(omitted);small=dict(observed,sites=observed['sites'][:1])
    try:partial.removal_site_inventory(small)
    except OperatorError as error:assert 'Unknown sharing database' in str(error);inventory_reason=str(error)
    else:raise AssertionError('Partial sharing inventory accepted')
    try:observer.state(observed,catalog)
    except PlanningError as error:assert 'Database installation metadata differs from verified artifact' in str(error);proposal_reason=str(error)
    else:raise AssertionError('Incompatible native versions accepted in shared runtime')
    (OUTPUT/'shared-runtime-observation.json').write_text(json.dumps(observed,indent=2)+'\n',encoding='utf8')
    reports=[]
    for label,expected in [('original-pin','Database release inventory differs'),('matching-pin-still-incompatible','Native module state/version differs')]:
        if label=='matching-pin-still-incompatible':sql(reader,"UPDATE ir_config_parameter SET value='"+state['inventory_digest']+"' WHERE key='mp.active_inventory_digest';")
        name=state['project']+'-incompatible-'+label;args=['docker','create','--name',name,'--label','com.modular.qualification=G5-tenant-isolation','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_runtime','--memory','768m','--pids-limit','128','--tmpfs','/tmp','--mount','type=volume,source='+volume+',target=/run/secrets,volume-subpath=config,readonly','--mount','type=volume,source='+volume+',target=/var/lib/modular,volume-subpath=data','-e','MP_EXPECTED_DATABASE='+database,'-e','MP_EXPECTED_INVENTORY_DIGEST='+state['inventory_digest'],state['image_id']]
        cid=command(args).decode().strip();state['containers'].append(dict(purpose=label,container_id=cid));save('checking_'+label);command(['docker','start',cid]);exit_code=int(command(['docker','wait',cid],timeout=90).decode().strip());assert exit_code!=0
        r=subprocess.run(['docker','logs',cid],capture_output=True,timeout=30);logs=r.stdout+r.stderr;(LOCAL/(label+'.log')).write_bytes(logs);assert expected.encode() in logs and b'odoo.modules.loading' not in logs
        item=json.loads(command(['docker','inspect',cid]))[0];assert not item['State']['Running'] and item['Config']['Entrypoint']==['/venv/bin/python','/opt/modular/tools/start_worker.py'] and not item['HostConfig']['PortBindings'];command(['docker','network','disconnect',state['project']+'_runtime',cid])
        assert json.loads(sql(reader,BUSINESS_SQL))==business and json.loads(sql(reader,SCHEMA))==schema
        reports.append(dict(case=label,container_id=cid,exit_code=exit_code,reason=expected,rejected_before_native_import=True,retained_stopped_disconnected=True,business_schema_exact=True))
    sql(reader,"UPDATE ir_config_parameter SET value='"+state['cases']['c']['source_inventory']+"' WHERE key='mp.active_inventory_digest';")
    assert json.loads(sql(source,BUSINESS_SQL))==before['business'] and json.loads(sql(source,SCHEMA))==before['schema'] and load(ROOT/'.local/operator/targets/g5.json')==main_config
    save('compatibility_verified');report=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),incompatible_actual_native_versions={'a':'19.0.0.2.2','c':'19.0.0.2.1'},proposal_rejection=proposal_reason,complete_database_inventory_verified=True,omitted_database_rejection=inventory_reason,cases=reports,only_test_pin_temporarily_changed_restored=True,no_native_version_rows_fabricated=True,source_main_unchanged=True,limits=['Copied genuine old release DB, not an actual upgrade or new installation.','One inventory-pin substitution isolates native-version rejection; never represented as a valid published release.','Current R1 requires separate deployments for incompatible native versions; no multi-version import isolation is claimed.'])
    dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',planner_refused=True,default_startup_refusals=2,complete_site_inventory=True)))


if __name__=='__main__':main()
