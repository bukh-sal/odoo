"""Continue exact imported fixture after the diagnosed empty-volume UID mismatch."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent/'setup';LOCAL=ROOT/'.local/g5-dispatch';SOURCE=ROOT/'.local/g5-lifecycle'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.catalog import Catalog
from modular_platform.deployment import DockerObserver
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from modular_platform.profile_channel import publish_profile
from modular_platform.workers import wait_ready
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql

COPY="""import json,os,pathlib,shutil,sys
data=json.load(sys.stdin);target=pathlib.Path('/target');source=pathlib.Path('/source/filestore')/data['source']
assert os.getuid()==10001 and target.stat().st_uid==10001 and not (target/'filestore').exists()
(target/'filestore').mkdir();shutil.copytree(source,target/'filestore'/data['database'])
assert all(p.stat().st_uid==10001 for p in [target,*(target.rglob('*'))])
"""


def main():
    load=lambda p:json.loads(p.read_text(encoding='utf8'));state=load(LOCAL/'state.json');source=load(SOURCE/'operator/target.json')
    assert state['phase']=='creating_stopped_worker_edge' and state['project']=='mp-r0-r1dispefb95a06d78f' and source['generation']==18
    assert not (LOCAL/'operator').exists();project=state['project'];database=state['active_db'];reader=DockerObserver(source)
    def command(args,*,input=None):
        r=subprocess.run(args,input=input,capture_output=True,timeout=180)
        if r.returncode:
            (LOCAL/'setup-resume.stderr').write_bytes(r.stderr);raise RuntimeError('Storage continuation failed; inspect exact targets, never replay database creation')
        return r.stdout
    compose=['docker','compose','--env-file',str(LOCAL/'compose.env'),'-f',str(ROOT/'deploy/compose.yaml'),'-f',str(LOCAL/'compose.override.json')]
    db=command(compose+['ps','-q','db']).decode().strip();assert db
    deployment=command(['docker','exec',db,'psql','-X','-qAt','-U','postgres','-d',database,'-c',"SELECT value FROM ir_config_parameter WHERE key='mp.deployment_id';"]).decode().strip()
    assert deployment!=source['deployment_id']
    for service in ['app','edge']:
        cid=command(compose+['ps','--all','-q',service]).decode().strip();info=json.loads(command(['docker','inspect',cid]))[0];assert info['State']['Status']=='created'
    evidence=dict(result='exact_existing_fixture_reconciliation',original_exec_session=69044,diagnosis='Root helper with dropped capabilities cannot write a UID10001-owned mode0755 volume.',observed_destination_uid=10001,observed_destination_gid=10001,destination_filestore_absent=True,database_recreation=False,new_private_secrets_generated=False,continuation_uid=10001)
    (OUTPUT/'storage-reconciliation.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf8')
    command(['docker','run','--rm','-i','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--mount','type=volume,source='+source['project']+'_filestore,target=/source,readonly','--mount','type=volume,source='+project+'_filestore,target=/target','--entrypoint','/venv/bin/python',source['image_id'],'-c',COPY],input=json.dumps(dict(source=source['sites'][0]['database'],database=database)).encode())
    state['phase']='starting_guarded_copy';(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    command(compose+['start','app','edge']);app=command(compose+['ps','-q','app']).decode().strip();app=json.loads(command(['docker','inspect',app]))[0]['Id']
    target=dict(source,project=project,deployment_id=deployment,sites=[dict(source['sites'][0],database=database)],worker_id=app)
    protect_directory(LOCAL/'operator');(LOCAL/'operator/target.json').write_text(json.dumps(target,indent=2)+'\n',encoding='utf8')
    OperatorStore.initialize(LOCAL/'operator/control',{deployment:[state['site_id']]},allow_noninteractive=True);wait_ready(app)
    fixture=load(SOURCE/'fixtures.json');fixture['database']=database;(LOCAL/'fixtures.json').write_text(json.dumps(fixture,indent=2)+'\n',encoding='utf8')
    observer=DockerObserver(target);catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True);observed=observer.state(observer.read(),catalog.snapshot())['state']
    before=json.loads(sql(reader,BUSINESS_SQL));schema=json.loads(sql(reader,SCHEMA));assert json.loads(sql(observer,BUSINESS_SQL))==before and json.loads(sql(observer,SCHEMA))==schema
    publish_profile(observer,catalog)
    state.update(phase='setup_verified',utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n',encoding='utf8')
    report=dict(result='passed_new_disposable_recovery_fixture',project=project,deployment_id=deployment,site_id=state['site_id'],database=database,port=state['port'],image_id=source['image_id'],generation=18,source_target_configuration_exact=load(SOURCE/'operator/target.json')==source,source_business_schema_exact=True,copied_reference_business_schema_exact=True,new_private_control_store=True,technical_credentials_revoked=True,session_secret_rotated=True,database_recreation=False)
    for name,value in [('setup.json',report),('state-before.json',observed),('business-before.json',before),('schema-before.json',schema),('configuration-before.json',target)]:
        with (OUTPUT/name).open('x',encoding='utf8') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
