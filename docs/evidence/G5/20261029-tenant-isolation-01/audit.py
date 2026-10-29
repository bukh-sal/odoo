"""Final source/protected-target/copy/container audit without native execution."""
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-tenant'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit.json';assert not dest.exists()
    global_catalog=Catalog(ROOT/'.local/operator/catalog',configuration(ROOT/'.local/operator/trust.json'),readonly=True).snapshot();assert len(global_catalog)==7
    protected=[]
    for name,target,baseline,business,digest in [
        ('main','.local/operator/targets/g5.json','docs/evidence/G5/20261028-manager-install-01/state-after-install.json','docs/evidence/G5/20261028-manager-install-01/observed-business-after.json','3441ea13f16aef9a26226059df88da2d8992fdb2db95f491e98e0513d41b72c9'),
        ('manager','.local/g5-manager-upgrade/operator/target.json','docs/evidence/G5/20261029-migration-order-rollout-01/state-after.json','docs/evidence/G5/20261029-migration-order-rollout-01/business-after.json','8c586a0832f8d0147c3ab491a7897d34d0882d0bd97eecb4fc302df8aa98f8ad')]:
        path=ROOT/target;config=load(path);reader=DockerObserver(config);assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
        assert reader.state(reader.read(),global_catalog)['state']==load(ROOT/baseline)
        actual=json.loads(sql(reader,BUSINESS_SQL)) if name=='main' else snapshot(reader);assert actual==load(ROOT/business)
        protected.append(dict(target=name,generation=config['generation'],full_state_business_configuration_exact=True))
    life_state=load(ROOT/'.local/g5-lifecycle/state.json');life=load(ROOT/'.local/g5-lifecycle/operator/target.json');catalog=Catalog(ROOT/life_state['operator_catalog'],configuration(ROOT/life_state['operator_trust_config']),readonly=True).snapshot();assert len(catalog)==8
    for name,target,baseline in [('lifecycle','.local/g5-lifecycle/operator/target.json','docs/evidence/G5/20261029-worker-fence-01/deploy'),('dispatch','.local/g5-dispatch/operator/target.json','docs/evidence/G5/20261029-dispatch-fence-01/recovery')]:
        config=load(ROOT/target);folder=ROOT/baseline;reader=DockerObserver(config);suffix='after' if name=='lifecycle' else 'restored'
        assert config==load(folder/('configuration-'+suffix+'.json'))
        assert reader.state(reader.read(),catalog)['state']==load(folder/('state-'+suffix+'.json'))
        assert json.loads(sql(reader,BUSINESS_SQL))==load(folder/('business-'+suffix+'.json')) and json.loads(sql(reader,SCHEMA))==load(folder/('schema-'+suffix+'.json'))
        assert files(reader)==load(folder/('files-'+suffix+'.json'))
        with sqlite3.connect((ROOT/target).parent/'control/control.sqlite3') as db:states=[list(r) for r in db.execute('SELECT state,count(*) FROM operations GROUP BY state')]
        assert states==([['completed',17],['failed_before_mutation',3],['revoked',4]] if name=='lifecycle' else [['revoked',1]])
        protected.append(dict(target=name,generation=config['generation'],full_state_business_schema_files_configuration_exact=True,operation_states=states))
    state=load(LOCAL/'state.json');assert state['phase']=='compatibility_verified' and len(state['cases'])==3 and len(state['containers'])==9
    for case,row in state['cases'].items():
        reader=DockerObserver(dict(life,project=state['project'],sites=[dict(database=row['database'],site_id=row['site_id'])]))
        assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup'/(case+'-business.json')) and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup'/(case+'-schema.json'))
        if case=='c':assert json.loads(sql(reader,"SELECT to_jsonb(value) FROM ir_config_parameter WHERE key='mp.active_inventory_digest';"))==row['source_inventory']
    removed=load(ROOT/'.local/g5-lifecycle/worker-fence-matrix.json')['databases']['removed'];reader=DockerObserver(dict(life,sites=[dict(life['sites'][0],database=removed['database'])]))
    before=load(OUTPUT/'setup/source-b.json');assert json.loads(sql(reader,BUSINESS_SQL))==before['business'] and json.loads(sql(reader,SCHEMA))==before['schema']
    containers=[]
    for row in state['containers']:
        item=json.loads(subprocess.check_output(['docker','inspect',row['container_id']]))[0];assert not item['State']['Running'] and not item['NetworkSettings']['Networks'] and not item['HostConfig']['PortBindings']
        containers.append(dict(row,exit_code=item['State']['ExitCode'],stopped_disconnected=True))
    network=json.loads(subprocess.check_output(['docker','network','inspect',state['project']+'_runtime']))[0];assert network['Internal'] and len(network['Containers'])==1
    db=json.loads(subprocess.check_output(['docker','inspect',state['db_container']]))[0];assert db['State']['Running'] and not db['HostConfig']['PortBindings']
    source_paths=['packages/platform_sdk/modular_platform/worker_start.py','packages/platform_sdk/modular_platform/deployment.py','packages/platform_sdk/modular_platform/projection.py','packages/platform_sdk/modular_platform/artifact_removal.py','tools/start_worker.py','platform_addons/mp_identity/scopes.py','platform_addons/mp_identity/models/scoped.py','platform_addons/mp_core/dispatch.py','platform_addons/mp_example_notes/models.py','platform_addons/mp_example_notes_labels/models.py','odoo/orm/registry.py','odoo/http.py','addons/web/controllers/session.py']
    runtime=load(OUTPUT/'shared-runtime-observation.json')['runtime'];source={}
    for path in source_paths:
        digest=hashlib.sha256((ROOT/path).read_bytes()).hexdigest();native=path.replace('platform_addons/','addons/')
        if native in runtime['inventory']['files']:assert runtime['inventory']['files'][native]==digest,path
        else:
            assert path=='tools/start_worker.py'
            command=['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--entrypoint','/venv/bin/python',state['image_id'],'-c',"import hashlib;from pathlib import Path;print(hashlib.sha256(Path('/opt/modular/tools/start_worker.py').read_bytes()).hexdigest())"]
            assert subprocess.check_output(command,timeout=30).decode().strip()==digest
        source[path]=digest
    # Existing bootstrap tests remain current: bind their source, rather than
    # rerunning unchanged checks as a substitute for the new integration cases.
    prior=load(ROOT/'docs/evidence/G5/20261029-worker-fence-01/source-boundary.json')['source_sha256'];assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in prior.items())
    for filename in ['registry-qualification.json','http-qualification.json','compatibility-qualification.json']:assert load(OUTPUT/filename)['result']=='passed'
    for label in ['ab','ba']:assert load(OUTPUT/('registry-'+label+'.json'))['inside_source_sha256']==hashlib.sha256((OUTPUT/'inside.py').read_bytes()).hexdigest()
    for case in ['a','b']:assert load(OUTPUT/('http-'+case+'.json'))['source_sha256']==hashlib.sha256((OUTPUT/'http_inside.py').read_bytes()).hexdigest()
    frozen=load(ROOT/'docs/contracts/freeze-v1.json');assert len(frozen['files'])==87 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['files'].items())
    private={p.read_text(encoding='utf8').strip().encode() for p in LOCAL.glob('*password')};private|={p.read_text(encoding='utf8').strip().encode() for p in [ROOT/'.local/g5-lifecycle/bootstrap-password',ROOT/'.local/g5/bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password'] if p.exists()};count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not v or v not in raw for v in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,source_sha256=source,runtime_image=state['image_id'],runtime_inventory_digest=state['inventory_digest'],prior_bootstrap_tests_source_still_current=True,frozen_files=87,owned_databases=list(state['cases'].values()),business_schema_exact_all_copies=True,removed_source_copy_exact=True,containers=containers,only_owned_DB_server_still_connected=True,public_ports_none=True,public_files_checked=count,known_private_values_checked=len(private),limits=['Bounded evidence scan, not SEC03 release qualification.','No production source changes or new runtime image; actual runtime bytes equal current qualifying host paths.','Failed empty-stdin, namespace-init and raw-SQL-before-flush harness attempts are retained/excluded, not counted as passes.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',protected_targets=4,source_files=len(source),owned_containers_stopped=len(containers),public_files_checked=count)))


if __name__=='__main__':main()
