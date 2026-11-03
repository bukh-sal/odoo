"""Continue existing initialized copy; explicit unavailable external authority."""
import copy,hashlib,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-production-profile-01';SOURCE=ROOT/'.local/g7-fresh-release-01/target21'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools')]
from modular_platform.deployment import DockerObserver
from modular_platform.catalog import Catalog
from modular_platform.plans import data_digest
from modular_platform.profile_channel import publish_profile
from modular import configuration
from lifecycle_data_probe import BUSINESS_SQL,SCHEMA,sql
load=lambda p:json.loads(p.read_text());state=load(LOCAL/'state.json');source=load(SOURCE/'operator/target.json');target=load(LOCAL/'operator/target.json')
assert state['phase']=='starting_production_edge' and source['generation']==4
app=next(c['container_id'] for c in state['containers'] if c['purpose']=='application')
assert target['worker_id']==app and target['image_id']==source['image_id']
for entry in state['containers']:
 item=json.loads(subprocess.check_output(['docker','inspect',entry['container_id']]))[0];assert item['State']['Running']
# No worker-target, issuer or publication is copied. This is a native HTTP/TLS
# qualification realm with explicitly unavailable optional external analysis.
assert not (LOCAL/'operator/worker-target.json').exists()
volume_names=subprocess.check_output(['docker','volume','ls','-q']).decode().split()
assert not any(v.startswith(state['project']) and ('authority' in v or 'worker' in v or 'public-config' in v) for v in volume_names)
empty=dict(endpoints=[],service_health={})
expected=json.loads(json.dumps(source['published_release']).replace(source['sites'][0]['site_id'],state['site_id']))
target['published_release']=expected
own=DockerObserver(target,external_reader=lambda:copy.deepcopy(empty));source_reader=DockerObserver(source)
# Independent fresh clone bootstrap; do not infer a new lifecycle operation or
# silently drop published metadata plugins to make the resolver pass.
prior=json.loads(sql(own,"SELECT to_jsonb(value) FROM ir_config_parameter WHERE key='mp.release_digest';"));assert prior==data_digest(source['published_release'])
changed=json.loads(sql(own,"UPDATE ir_config_parameter SET value='"+data_digest(expected)+"' WHERE key='mp.release_digest' AND value='"+prior+"' RETURNING to_jsonb(value);"));assert changed==data_digest(expected)
(LOCAL/'operator/target.json').write_text(json.dumps(target,indent=2)+'\n')
# A real native read confirms there are no active copied technical credentials.
assert json.loads(sql(own,"SELECT to_jsonb(count(*)) FROM mp_service_credential WHERE state='active';"))==0
catalog=Catalog(ROOT/state['operator_catalog'],configuration(ROOT/state['operator_trust_config']),readonly=True)
observation=own.read();document=own.state(observation,catalog.snapshot())['state'];assert document['release_lock']==expected
profile=publish_profile(own,catalog)
schema=json.loads(sql(own,SCHEMA));assert schema==json.loads(sql(source_reader,SCHEMA))
for name,value in [('source-business',json.loads(sql(source_reader,BUSINESS_SQL))),('source-schema',schema),('business-before',json.loads(sql(own,BUSINESS_SQL))),('schema-before',schema),('state-before',document),('configuration',target)]:
 path=OUT/'setup'/(name+'.json');assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n')
assert load(SOURCE/'operator/target.json')==source
state.update(phase='profiles_started_ready',external_analysis='explicitly_unavailable_no_worker_or_issuer_copied',utc=datetime.now(timezone.utc).isoformat());(LOCAL/'state.json').write_text(json.dumps(state,indent=2)+'\n')
record=dict(result='passed_current_production_profile_setup_only',utc=state['utc'],project=state['project'],application_image=state['image_id'],proxy_image='sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f',database=state['active_db'],site_id=state['site_id'],generation=4,ports=dict(development=18092,redirect=18093,TLS=18445),configuration_sha256=hashlib.sha256((LOCAL/'odoo.conf').read_bytes()).hexdigest(),named_accounts_rotated=4,admin_inactive=True,technical_credentials_active=0,external_authority=empty,source_target_unchanged=True,schema_exact=True,limits=['Isolated owned qualification copy, not fresh installation, external worker qualification or production deployment.','External analysis unavailable by explicit absence of operator publisher/issuer; do not fabricate a healthy endpoint or remove metadata pins.','Production_preflight, HTTP/TLS/rate/security matrix and cleanup still required; no G7 acceptance pass.'])
(OUT/'setup/qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
