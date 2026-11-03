"""One reusable owned qualification realm; no existing DB/filestore is copied."""
import argparse,hashlib,importlib.util,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
spec=importlib.util.spec_from_file_location('fresh_release_network_recipe',ROOT/'docs/evidence/G6/20261029-events-01/fixture.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
f=previous.f;LOCAL=ROOT/'.local/g7-fresh-release-01';f.LOCAL=LOCAL;f.OUTPUT=OUT/'site'
f.PROTECTED=[*f.PROTECTED,'.local/g6-events/operator/target.json','.local/g6-events/operator/worker-target.json']
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image
from modular import configuration
OLD='sha256:31a673ebbc53fbdecbc5cbfdb5f0eac30d11367630da306d47b5e14cfce17345'
NEW='sha256:570275717add25f201d315ebfbd71ca63882bf7f4a6a7708077ae9e18ebc1886'
def curate(build,runtime,project):
 assert runtime['platform_version']=='0.1.20' and build['image_id']==OLD
 # Only the fresh copied test catalog is replaced, before any reader is opened.
 # Copy artifacts/trust, never the original private approval store or app data.
 source=ROOT/'.local/g6-events/operator';destination=LOCAL/'operator'
 shutil.copyfile(source/'trust.json',destination/'trust.json')
 shutil.copytree(source/'catalog',destination/'catalog',dirs_exist_ok=True)
 catalog=Catalog(destination/'catalog',configuration(destination/'trust.json'),readonly=True)
 rows=catalog.snapshot();assert len(rows)==19
 current=inspect_image(NEW);assert current['platform_version']=='0.1.21'
 assert runtime['python_metadata']!=current['python_metadata'] and runtime['python_lock_digest']!=current['python_lock_digest']
 f.save('baseline-and-target.json',dict(result='observed_existing_real_dependency_baseline_and_target',baseline_image=OLD,baseline_inventory=runtime['inventory_digest'],target_image=NEW,target_inventory=current['inventory_digest'],baseline_platform='0.1.20',target_platform='0.1.21',python_metadata_changed=True,baseline_python_lock=runtime['python_lock_digest'],target_python_lock=current['python_lock_digest'],copied_curated_archives=len(rows),independent_new_control=True,no_database_filestore_operator_store_copied=True))
def configure():
 assert not LOCAL.exists() and not (OUT/'site').exists()
 f.configure(build_path=ROOT/'docs/evidence/G7/20261102-core20-candidate-04/candidate-build.json',core_version='19.0.0.1.20',hostname='g7qual.localhost',port_start=18090,curator=curate,project_prefix='mp-g7-qual-',database_prefix='mp_disposable_r0_r1_g6_g7qual_')
 previous.networks(f.load(LOCAL/'state.json'))
 state=f.load(LOCAL/'state.json');volume=state['project']+'_pgdata'
 assert volume in state['owned_resources']['volumes']
 f.command('create-owned-pgdata',['docker','volume','create','--label','com.modular.disposable='+state['project'],'--label','com.docker.compose.project='+state['project'],'--label','com.docker.compose.volume=pgdata',volume])
 f.save('ownership.json',dict(result='owned_fresh_qualification_realm_configured',project=state['project'],site_id=state['site_id'],deployment_id=state['deployment_id'],resources=state['owned_resources'],port=state['port'],url=state['url'],no_existing_user_data=True,purpose='Actual dependency fault/recovery, then full fresh target initialization/release qualification/runbooks in this same project'))
 print(json.dumps(dict(result='fresh_realm_configured',project=state['project'],database=state['active_db'],port=state['port'])))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['configure','initialize','install']);a=p.parse_args()
 if a.action=='configure':configure()
 else:getattr(f,a.action)()
