"""Preflight existing adapter naming before allocating the replacement realm."""
import json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from fixture import f,LOCAL,OUT,ROOT,OLD,curate,previous
from modular_platform.deployment import DockerObserver
assert not LOCAL.exists() and not (OUT/'site').exists()
refused=f.load(ROOT/'.local/g7-fresh-release-01-project-refused/state.json');assert refused['phase']=='archived_refused_project_retired'
prefix='mp-r0-r1g7qual';dbprefix='mp_disposable_r0_r1_g6_g7qual_'
DockerObserver(dict(schema_version=1,deployment_id=str(uuid4()),project=prefix+'000000000000',sites=[dict(site_id=str(uuid4()),database=dbprefix+'000000000000')],image_id=OLD,generation=1,policy_version=1,operator_authorization_generation=1,release_created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')))
build=ROOT/'docs/evidence/G7/20261102-notes8-labels4-candidate-04/candidate-build.json';assert f.load(build)['image_id']==OLD
f.configure(build_path=build,core_version='19.0.0.1.20',hostname='g7qual.localhost',port_start=18090,curator=curate,project_prefix=prefix,database_prefix=dbprefix)
state=f.load(LOCAL/'state.json');previous.networks(state);volume=state['project']+'_pgdata'
assert subprocess.run(['docker','volume','inspect',volume],capture_output=True,timeout=10).returncode!=0
f.command('create-owned-pgdata',['docker','volume','create','--label','com.modular.disposable='+state['project'],'--label','com.docker.compose.project='+state['project'],'--label','com.docker.compose.volume=pgdata',volume])
f.save('ownership.json',dict(result='owned_existing_adapter_compatible_fresh_realm_configured',project=state['project'],resources=state['owned_resources'],site_id=state['site_id'],deployment_id=state['deployment_id'],url=state['url'],adapter_syntax_checked_before_allocation=True,refused_project_archived_retired=True,no_original_data_or_store_copied=True,images_built=0,purpose='Actual dependency fault/recovery, then genuine target fresh initialization/release/runbooks in same project'))
print(json.dumps(dict(result='fresh_realm_configured',project=state['project'],database=state['active_db'],port=state['port'])))
