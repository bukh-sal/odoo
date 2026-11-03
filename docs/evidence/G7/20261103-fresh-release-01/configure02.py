"""Correct exact baseline reference after pre-Docker curator refusal."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from fixture import f,LOCAL,OUT,ROOT,OLD,curate,previous
assert not LOCAL.exists() and not (OUT/'site').exists()
refused=ROOT/'.local/g7-fresh-release-01-config-refused';assert refused.is_dir() and not (refused/'state.json').exists() and not (refused/'operator/control').exists()
build=ROOT/'docs/evidence/G7/20261102-notes8-labels4-candidate-04/candidate-build.json'
assert f.load(build)['image_id']==OLD
f.configure(build_path=build,core_version='19.0.0.1.20',hostname='g7qual.localhost',port_start=18090,curator=curate,project_prefix='mp-g7-qual-',database_prefix='mp_disposable_r0_r1_g6_g7qual_')
previous.networks(f.load(LOCAL/'state.json'))
state=f.load(LOCAL/'state.json');volume=state['project']+'_pgdata';assert volume in state['owned_resources']['volumes']
f.command('create-owned-pgdata',['docker','volume','create','--label','com.modular.disposable='+state['project'],'--label','com.docker.compose.project='+state['project'],'--label','com.docker.compose.volume=pgdata',volume])
f.save('ownership.json',dict(result='owned_fresh_qualification_realm_configured',project=state['project'],site_id=state['site_id'],deployment_id=state['deployment_id'],resources=state['owned_resources'],port=state['port'],url=state['url'],no_existing_user_data=True,purpose='Actual dependency fault/recovery, then full fresh target initialization/release qualification/runbooks in this same project',previous_attempt='Wrong earlier core20 build metadata refused in curator before state/secrets/Docker mutations; scaffold retained privately, exact31 baseline now selected'))
print(json.dumps(dict(result='fresh_realm_configured',project=state['project'],database=state['active_db'],port=state['port'])))
