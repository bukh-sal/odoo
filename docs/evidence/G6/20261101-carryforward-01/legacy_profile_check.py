"""Read the protected legacy no-dispatch DB through the new host branches."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G6/20261029-events-01')]
import fixture as j
from modular import configuration
from modular_platform.native_executor import NativeExecutor
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.dispatch_operator import DispatchMaintenance
f=j.f;f.OUTPUT=OUT;current=f.load(j.LOCAL/'state.json');f.guard(current)
folder=ROOT/'.local/g5-clean-recovery';config=f.load(folder/'operator/target.json');assert config['generation']==4
name=config['project']+'-db-1';info=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
assert info['Name']=='/'+name and info['State']['Status']=='exited' and info['State']['ExitCode']==0
assert config['project']=='mp-r0-r1cleand32d742ed8b4'
marker=j.LOCAL/'legacy-profile-check-01.json';assert not marker.exists();f.write(marker,dict(state='starting_exact_stopped_legacy_database',container_id=info['Id']))
f.command('legacy-profile-start-db-01',['docker','start',info['Id']])
ready=subprocess.run(['docker','exec',info['Id'],'pg_isready','-U','postgres'],capture_output=True);assert ready.returncode==0,'Inspect same DB readiness; never recreate'
try:
    native=NativeExecutor(OperatorStore(folder/'operator/control'),folder/'operator/target.json',folder/'operator/catalog',configuration(folder/'operator/trust.json'))
    effects=RestoreExecutor(native)._supported_effects(config['sites'][0]['database'])
    assert effects==dict(job_table=False,outbox_table=False,api_key_count=0,active_technical_credentials=0,external_installations=0)
    helper=DispatchMaintenance(native);assert helper.present() is False and helper.inspect() is None
    assert hashlib.sha256((folder/'operator/target.json').read_bytes()).hexdigest()==current['protected_configurations']['.local/g5-clean-recovery/operator/target.json']
finally:f.command('legacy-profile-stop-db-01',['docker','stop','--time','20',info['Id']])
after=json.loads(subprocess.check_output(['docker','inspect',info['Id']]))[0];assert not after['State']['Running'] and after['State']['ExitCode']==0
result=dict(result='passed_real_legacy_readonly_profile',container_id=info['Id'],project=config['project'],generation=4,effects=effects,presence_false_and_no_native_child=True,configuration_exact=True,original_stopped_state_restored=True,no_DB_or_filestore_or_user_mutation=True,limits=['Targeted legacy profile/source revalidation with retained actual G5 workflow evidence; no replay of its completed restore or installation.'])
f.save('legacy-profile.json',result);f.write(marker,dict(state='completed',result='passed'));f.guard(current);print('Protected G5 legacy profile still rejects dispatch and remains unchanged/stopped after read-only check.')
