"""Approve reference provider/connector separately, then verify one original-actor job."""
from __future__ import annotations
import argparse,json,sys,tomllib
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
sys.dont_write_bytecode=True;sys.path.insert(0,str(Path(__file__).resolve().parent))
from initialize_reference import ROOT,Reference,load,write
from check_reference import Client
from modular import configuration
from modular_platform.catalog import Catalog
from modular_platform.lifecycle_planning import prepare_current_install_targets,installation_id
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.worker_operator import WorkerOperator

class Integration:
    def __init__(self,args):
        self.ref=Reference(args);self.state=self.ref.state();self.local=self.ref.local/'worker';self.marker=self.local/'integration.json'
        assert load(self.local/'state.json')['phase']=='scoped_worker_published_metadata_not_installed'
        self.target=self.ref.local/'operator/target.json';self.store=self.ref.local/'operator/control';self.catalog=self.ref.private/'catalog';self.trust=self.ref.local/'operator/trust.json'
        self.prefix=[sys.executable,'-I',str(ROOT/'tools/modular.py'),'--config',str(self.trust)]
        self.options=['--deployment-config',str(self.target),'--catalog',str(self.catalog)]
    def phase(self,record,name):record['phase']=name;write(self.marker,record);print(json.dumps(dict(integration_phase=name)),flush=True)
    def apply(self,record,label,bundle):
        path=self.local/(label+'-bundle.json');write(path,bundle)
        record[label]=dict(operation_id=bundle['plan']['operation_id'],plan_hash=bundle['plan_hash']);self.phase(record,label+'_registering')
        ops=self.prefix+['operations','--store',str(self.store)];operation=bundle['plan']['operation_id']
        self.ref.command(label+'-register',ops+['register','--bundle',str(path),*self.options])
        self.ref.command(label+'-approve',ops+['approve',operation,'--plan-hash',bundle['plan_hash'],'--noninteractive','--ack-trust','--ack-permissions',*self.options])
        self.phase(record,label+'_applying')
        result=json.loads(self.ref.command(label+'-apply',self.prefix+['plugin','apply',operation,'--store',str(self.store),*self.options],timeout=600));assert result['state']=='completed'
        write(self.local/(label+'-completed.json'),result)
    def native(self):return NativeExecutor(OperatorStore(self.store),self.target,self.catalog,configuration(self.trust))
    def register(self):
        assert not self.marker.exists(),'Inspect prior integration rather than replay registration'
        record=dict(phase='preparing_provider');write(self.marker,record)
        scope=load(self.local/'state.json')['scope'];manifest=tomllib.loads((ROOT/'plugins/document_stats/plugin.toml').read_text())
        pins=[row for row in load(self.ref.kit/'plugins/index.json')['packages'] if row['plugin_id']==manifest['plugin']['id'] and row['version']==manifest['plugin']['version']];assert len(pins)==1
        nomination=dict(operation_type='install',targets=[dict(scope,plugin_id=manifest['plugin']['id'],action='install')],selections=[{key:pins[0][key] for key in ['plugin_id','version','digest']}],feature_states=[dict(scope,availability='enabled')])
        path=self.local/'provider-nomination.json';write(path,nomination)
        bundle=json.loads(self.ref.command('provider-plan',self.prefix+['plugin','plan-external','--input',str(path),'--store',str(self.store),*self.options]))
        assert len(bundle['plan']['artifacts'])==1 and bundle['plan']['artifacts'][0]['runtime']=='external_service'
        self.apply(record,'provider',bundle)
        native=self.native();snapshot=Catalog(self.catalog,configuration(self.trust),readonly=True).snapshot();current=native.observer.state(native.observer.read(),snapshot)['state']
        installation=next(i for i in current['installations'] if i['installation_id']==scope['installation_id'] and i['workspace_id']==scope['workspace_id'])
        assert installation['feature_state']=='enabled' and current['service_health'][scope['installation_id']+':'+scope['workspace_id']]['state']=='healthy'
        self.phase(record,'provider_metadata_enabled')
    def connect(self):
        record=load(self.marker);assert record['phase']=='provider_metadata_enabled'
        native=self.native();rows=Catalog(self.catalog,configuration(self.trust),readonly=True).snapshot();observed=native.observer.read();document=native.observer.state(observed,rows)
        scope=load(self.local/'state.json')['scope'];plugin='org.example.notes_stats'
        targets=[dict(installation_id=installation_id(observed['sites'][0],plugin),site_id=scope['site_id'],workspace_id=scope['workspace_id'],plugin_id=plugin,action='install')]
        bundle=prepare_current_install_targets(document,observed['sites'],rows,activation_targets=targets,operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        self.apply(record,'connector',bundle)
        native=self.native();current=native.observer.state(native.observer.read(),rows)['state'];write(self.ref.local/'installed-state.json',current)
        installation=next(i for i in current['installations'] if i['plugin_id']==plugin and i['workspace_id']==scope['workspace_id'])
        assert installation['feature_state']=='enabled'
        assert any(b['consumer_installation_id']==installation['installation_id'] and b['workspace_id']==scope['workspace_id'] and b['alias']=='stats' and b['provider_installation_id']==scope['installation_id'] for b in current['bindings'])
        self.phase(record,'native_connector_installed')
    def job(self):
        record=load(self.marker);assert record['phase']=='native_connector_installed'
        client=Client(self.ref,'alice');ident=load(self.ref.local/'reference-checks.json')['notes']['A']['id']
        note=client.service('org.example.notes','documents','get',dict(note_id=ident));self.phase(record,'enqueueing_original_actor_job')
        queued=client.service('org.example.notes_stats','jobs','analyze',dict(note_id=ident,expected_revision=note['revision']),key=str(uuid4()))['job']
        assert queued['state']=='pending';record['job_id']=queued['id'];self.phase(record,'running_one_guarded_job')
        runner=self.prefix+['worker','--store',str(self.store),'--deployment-config',str(self.target),'--worker-config',str(self.ref.local/'operator/worker-target.json'),'run-job-once']
        result=json.loads(self.ref.command('reference-run-one-job',runner,timeout=180));write(self.local/'job-runner-result.json',result)
        job=client.service('org.example.notes_stats','jobs','status',dict(note_id=ident))['job']
        text=note['body'];assert job['id']==record['job_id'] and job['state']=='completed' and job['attempts']==1 and job['error_code'] is None
        assert job['result']==dict(note_id=ident,revision=note['revision'],statistics=dict(characters=len(text),words=len(text.split()),lines=len(text.splitlines())))
        operator=WorkerOperator(OperatorStore(self.store),self.target,self.ref.local/'operator/worker-target.json');document=operator.publisher._document();entry=document['endpoints'][0]
        attestation=operator.observer(entry['descriptor'],operator.publisher._key_digest(entry['descriptor']),entry['key_id'])
        assert attestation==load(self.local/'qualified-runtime.json')['attestation'],'Worker runtime changed across metadata/native installation/job'
        write(self.local/'job-qualified.json',dict(job=job,publication_generation=document['generation'],worker_attestation=attestation,notes=2,boards=1,limits=['One reference original-actor job; retained G6/G7 outage/recovery qualifications remain separately scoped.']))
        self.phase(record,'reference_job_qualified');self.ref.phase(self.state,'kit_backend_worker_reference_qualified')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['register','connect','job']);parser.add_argument('--kit',type=Path,required=True);parser.add_argument('--workdir',type=Path,required=True);args=parser.parse_args();getattr(Integration(args),args.action)()
