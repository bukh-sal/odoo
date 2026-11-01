"""OS-only outbound stateless reference profile; native defaults stay closed.

Every request rebuilds a policy from the independently selected release/catalog,
protected worker configuration/publication and exact read-only DB metadata. This
is neither an app approval channel nor general external-effect reconciliation.
"""
from pathlib import Path
from .catalog import Catalog
from .contracts import load_json
from .deployment import _run,DockerObserver
from .dispatch_operator import DispatchMaintenance
from .metadata_sql import METADATA_SELECT
from .operator_os import OperatorError
from .plans import data_digest
from .worker_operator import WorkerPlanningReader,private_json


def reference_observer(native,configuration):
    def fresh():
        reader=WorkerPlanningReader(native.store,native.target_path,native.target_path.with_name('worker-target.json'))
        if reader.target not in (native.config,configuration):
            raise OperatorError('Independent deployment configuration changed during reference lifecycle')
        if any(reader.target[k]!=configuration[k] for k in ['deployment_id','project','sites']):
            raise OperatorError('Reference observer cannot change its independently selected site')
        return reader.planning_state()
    return DockerObserver(configuration,external_reader=fresh)


def read_metadata(native,configuration):
    query="BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='5s'; "+METADATA_SELECT+' ROLLBACK;'
    value=load_json(_run(['docker','exec','-i',native.observer._container('db'),'psql','-X','-qAt','-U','postgres',
        '-d',configuration['sites'][0]['database'],'-v','ON_ERROR_STOP=1'],input=query.encode()))
    if value['site_id']!=configuration['sites'][0]['site_id']:raise OperatorError('Reference metadata site changed')
    return value


class ReferenceDispatchMaintenance(DispatchMaintenance):
    def __init__(self,native):
        super().__init__(native);self.policies={}

    def reference_policy(self,configuration):
        self._configuration(configuration)
        worker_path=Path(self.native.target_path).absolute().with_name('worker-target.json')
        reader=WorkerPlanningReader(self.native.store,self.native.target_path,worker_path)
        if any(reader.target[k]!=configuration[k] for k in ['deployment_id','project','sites']):
            raise OperatorError('Reference worker must belong to the exact independently selected deployment/site')
        publication=reader.publisher._document();observed=reader.planning_state()
        metadata=read_metadata(self.native,configuration)
        catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
        selected={r['plugin_id']:r for r in configuration['published_release']['plugins']}
        registrations=[]
        for row in metadata['installations']:
            if row['runtime']=='native':continue
            pin=selected.get(row['plugin_id'])
            matches=[d for d in catalog if pin and d['manifest']['plugin']['id']==row['plugin_id'] and d['digest']==pin['digest']]
            if (row['plugin_id']!='org.example.document_stats' or row['metadata_state'] not in {'installed','removed'}
                    or len(matches)!=1 or row['digest']!=pin['digest'] or row['version']!=pin['version']
                    or row['manifest']!=matches[0]['manifest'] or data_digest(row['manifest'])!=pin['manifest_digest']
                    or row['manifest']['runtime']!={'kind':'external_service'}):
                raise OperatorError('External registration differs from independently pinned reference metadata')
            manifest=row['manifest'];features=[]
            for feature in metadata['features']:
                if feature['installation_id']!=row['installation_id']:continue
                if feature['plugin_id']!=row['plugin_id']:raise OperatorError('Reference feature ownership differs from installation')
                endpoints=[e for e in observed['endpoints'] if e['installation_id']==row['installation_id']
                    and e['workspace_id']==feature['workspace_id'] and e['endpoint_config']==manifest['external_service']['endpoint_config']]
                if row['metadata_state']=='removed':
                    if feature['feature_state']!='suspended' or any(e['state']!='revoked' for e in endpoints):
                        raise OperatorError('Retained reference metadata has active availability or endpoint approval')
                elif (len(endpoints)!=1 or endpoints[0]['expected_image_digest']!=manifest['external_service']['expected_image'].split('@',1)[1]
                        or manifest['external_service']['expected_image']!=reader.config['runtime']['image']):
                    raise OperatorError('Installed reference scope lacks its exact independently published endpoint/image')
                features.append({k:feature[k] for k in ['workspace_id','feature_state']})
            if row['metadata_state']=='removed' and any(g['installation_id']==row['installation_id'] and g['state']=='approved' for g in metadata['grants']):
                raise OperatorError('Removed reference installation retains approved grants')
            registrations.append(dict(installation_id=row['installation_id'],plugin_id=row['plugin_id'],version=row['version'],
                artifact_digest=row['digest'],manifest_digest=data_digest(manifest),state=row['metadata_state'],
                features=sorted(features,key=lambda f:f['workspace_id'])))
        if (reader.publisher._document()!=publication or private_json(worker_path)!=reader.config
                or private_json(self.native.target_path)!=reader.target):
            raise OperatorError('Independent reference publication/configuration changed during observation')
        value=dict(profile='r1-reference-stateless-v1',site_id=metadata['site_id'],runtime_image=reader.config['runtime']['image'],
            publication_digest=data_digest(publication),registrations=sorted(registrations,key=lambda r:r['installation_id']))
        self.policies[data_digest(value)]=value
        return value

    def run(self,action,operation,directory,**kwargs):
        if 'reference' in kwargs:raise OperatorError('Reference policy cannot originate in a caller proposal')
        configuration=kwargs.get('configuration') or self.native.config
        reference=self.reference_policy(configuration)
        return super().run(action,operation,directory,**kwargs,reference=reference)

    def require_profile(self,snapshot,*,closed=False):
        policy=self.policies.get(snapshot.get('reference_policy_digest')) if isinstance(snapshot,dict) else None
        if (not policy or snapshot.get('profile')!='r1-reference-stateless-dispatch-v1'
                or snapshot.get('state_digest')!=data_digest({k:v for k,v in snapshot.items() if k!='state_digest'})
                or snapshot.get('external_installations')!=len(policy['registrations'])
                or any(snapshot.get(k)!=0 for k in ['active_credentials','api_keys','uncertain_jobs'])
                or closed and (not snapshot.get('control') or snapshot['control']['state'] not in {'paused','restoring'})):
            raise OperatorError('Exact reconciled outbound reference profile required; unknown effects/credentials keep dispatch fenced')
        return snapshot
