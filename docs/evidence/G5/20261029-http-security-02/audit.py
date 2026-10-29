"""Current edge source/config, retained targets, bootstrap and recording audit."""
import ast
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;LOCAL=ROOT/'.local/g5-httpsecurity'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
from qualify_manager_upgrade_operation import snapshot,files
from http_profile import render


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));dest=OUTPUT/'final-audit-native.json';assert not dest.exists()
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
    state=load(LOCAL/'state.json');target=load(LOCAL/'operator/target.json');reader=DockerObserver(target);assert state['phase']=='profiles_started_ready' and state['project']=='mp-r0-r1http9669f0969d1d' and target['image_id']==life['image_id']
    assert reader.state(reader.read(),catalog)['state']==load(OUTPUT/'setup/state-before.json')
    assert json.loads(sql(reader,BUSINESS_SQL))==load(OUTPUT/'setup/business-before.json') and json.loads(sql(reader,SCHEMA))==load(OUTPUT/'setup/schema-before.json')
    assert load(LOCAL/'csrf-created-note.json')['state']=='deleted_verified'
    assert json.loads(sql(reader,"SELECT jsonb_build_object('old_logins',(SELECT count(*) FROM res_users WHERE active AND (login='admin' OR login ~ '^(g1_|r0_|r1_|g5_)')),'technical_credentials',(SELECT count(*) FROM mp_service_credential WHERE state='active'),'base_url',(SELECT value FROM ir_config_parameter WHERE key='web.base.url'),'frozen',(SELECT value FROM ir_config_parameter WHERE key='web.base.url.freeze'));"))==dict(old_logins=0,technical_credentials=0,base_url=state['origin'],frozen='True')
    prior_http=load(OUTPUT/'HTTP-qualification.json');assert load(OUTPUT/'native-rate-qualification.json')['result']=='passed'
    assert prior_http['result']=='passed_HTTP_matrix' and len(prior_http['checks'])==17
    profiles=[]
    for mode in ['development','production']:
        cid=next(r['container_id'] for r in state['containers'] if r['purpose']==mode+'-edge');actual=subprocess.check_output(['docker','exec',cid,'cat','/etc/nginx/conf.d/default.conf']).decode();expected=render(mode,state['origin'] if mode=='production' else None);assert actual==expected
        # Retain earlier authenticated HTTP checks only after proving that the
        # final config differs solely by the new separately tested rate handler.
        stripped=re.sub(r'map \$request_id \$mp_request_uuid \{\n.*?^\}\n','',actual,flags=re.M|re.S)
        stripped=re.sub(r'map \$uri \$mp_rate_error_body \{\n.*?^\}\n','',stripped,flags=re.M|re.S)
        stripped=stripped.replace('    error_page 429 = @mp_rate_limited;\n','')
        stripped=re.sub(r'^    location @mp_rate_limited \{\n.*?^    \}\n','',stripped,flags=re.M|re.S)
        assert stripped==(LOCAL/(mode+'-before-rate-json.conf')).read_text(encoding='utf8')
        profiles.append(dict(mode=mode,configuration_sha256=hashlib.sha256(actual.encode()).hexdigest(),prior_HTTP_policy_retained_except_separately_qualified_rate_handler=True))
    app=next(r['container_id'] for r in state['containers'] if r['purpose']=='application');appinfo=json.loads(subprocess.check_output(['docker','inspect',app]))[0];assert appinfo['State']['Running'] and appinfo['Config']['User']=='10001:10001' and appinfo['HostConfig']['ReadonlyRootfs'] and not appinfo['HostConfig']['PortBindings'] and set(appinfo['NetworkSettings']['Networks'])=={state['project']+'_runtime'}
    old=next(r['container_id'] for r in state['containers'] if r['purpose']=='failed-TLS-run-mount-hidden');item=json.loads(subprocess.check_output(['docker','inspect',old]))[0];assert not item['State']['Running'] and not item['NetworkSettings']['Networks']
    for name,expected in [('rate-TLS-qualification.json','passed'),('production-preflight.json','passed'),('source-Windows-final.json','passed'),('source-Linux-final.json','passed')]:assert load(OUTPUT/name)['result']==expected
    for name in ['source-Windows-final.json','source-Linux-final.json']:
        result=load(OUTPUT/name);assert result['tests']==5 and result['skipped']==0 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in result['source_sha256'].items())
    frozen=load(ROOT/'docs/contracts/freeze-v1.json');assert len(frozen['files'])==87 and all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen['files'].items())
    spec=importlib.util.spec_from_file_location('mp_http_probe',OUTPUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);fixture=load(LOCAL/'fixtures.json');sanity=[]
    for mode in ['development','production']:
        client=m.Client(mode);client.login(state,fixture,'alice');code,value,_,_=client.rpc('mp.example.note','search_count',[[]],workspace=fixture['workspaces']['A']['public_id']);assert code==200 and value['result']==2
        code,_,_,_=client.request('/web/login',headers={'Host':'attacker.invalid'});assert code==421
        code,_,_,_=client.request('/api/v1/session',headers={'Origin':'https://attacker.invalid'});assert code==403
        sanity.append(dict(mode=mode,final_source_native_auth_RPC_Host_Origin_passed=True))
    source_paths=['tools/http_profile.py','tools/production_preflight.py','deploy/nginx-r0.conf','deploy/compose-production.yaml','tests/test_http_profile.py'];source={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_paths}
    private={p.read_text(encoding='utf8').strip().encode() for p in LOCAL.glob('*password*') if p.is_file()}
    for p in [ROOT/'.local/g5-lifecycle/bootstrap-password',ROOT/'.local/g5/bootstrap-password',ROOT/'.local/g5-manager-upgrade/bootstrap-password']:
        if p.exists():private.add(p.read_text(encoding='utf8').strip().encode())
    canaries=load(LOCAL/'log-canaries.json');private.update(v.encode() for v in canaries.values())
    key=subprocess.check_output(['docker','run','--rm','--network','none','--read-only','--user','101:101','--cap-drop','ALL','--mount','type=volume,source='+state['project']+'_tls,target=/tls,readonly','--entrypoint','/venv/bin/python',state['image_id'],'-c',"import sys;from pathlib import Path;sys.stdout.buffer.write(Path('/tls/server.key').read_bytes())"],timeout=15);private.add(key);private.update(line for line in key.splitlines() if len(line)>32 and not line.startswith(b'-----'))
    count=0
    for p in OUTPUT.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        raw=p.read_bytes();assert all(not v or v not in raw for v in private),p.name
        if p.suffix=='.json':json.loads(raw)
        if p.suffix=='.py':ast.parse(raw)
        count+=1
    value=dict(result='passed',utc=datetime.now(timezone.utc).isoformat(),protected_targets=protected,active_fixture_project=state['project'],application_image_unchanged=target['image_id'],native_source_or_public_contract_changed=False,profiles=profiles,final_source_sanity=sanity,source_sha256=source,old_failed_edge_stopped_disconnected=True,current_backend_internal_nonroot_readonly=True,existing_business_schema_and_publication_exact=True,windows_tests=5,linux_tests=5,skipped=0,frozen_files=87,public_files_checked=count,known_private_values_and_key_fragments_checked=len(private),limits=['Bounded evidence/log canary scan; full release-wide SEC03 remains.','Explicit local test-copy bootstrap changed only site-scoped publication, user credentials and config; no install/upgrade/restore acceptance credit.','Self-signed local TLS profile is not an authorized external production deployment.'])
    dest.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result='passed',protected_targets=4,profiles=2,public_files_checked=count,source_files=len(source))))


if __name__=='__main__':main()
