"""Private recovery context: known base/target metadata, current OS authority.

No publication or credential is restored by this module. Source inspection can
recognize only the exact independently recorded checkpoint/approved target; a
fresh restored DB must use the reviewed checkpoint-derived epoch.
"""
import copy
from .deployment import DockerObserver
from .operator_os import OperatorError
from .plans import data_digest
from .reference_dispatch import ReferenceDispatchMaintenance
from .worker_operator import WorkerPlanningReader


def reference_needed(native,bundle,manifest=None):
    releases=[native.config.get('published_release',{}),bundle['operation_lock'].get('release',{})]
    if manifest:releases.append(manifest['configuration'].get('published_release',{}))
    return (any(p.get('runtime')=='external_service' for lock in releases for p in lock.get('plugins',[]))
        or any(a.get('runtime')=='external_service' for a in bundle['plan'].get('artifacts',[]))
        or ((manifest or {}).get('dispatch_profile') or {}).get('profile')=='r1-reference-stateless-dispatch-v1')


class ReferenceRecoveryDispatch(ReferenceDispatchMaintenance):
    def _transition_source(self,configuration):
        return self.bundle['plan']['operation_id'],self.base,True

    def __init__(self,native,bundle,manifest,*,purpose='restored'):
        super().__init__(native)
        if purpose not in {'source_inspection','restored','unchanged'}:raise OperatorError('Typed reference recovery purpose required')
        self.bundle,self.manifest,self.purpose=copy.deepcopy(bundle),copy.deepcopy(manifest),purpose
        if bundle['plan']['operation_id']!=manifest['operation_id'] or bundle['plan_hash']!=manifest['plan_hash']:
            raise OperatorError('Reference recovery must match the exact private checkpoint/operation')
        self.base=manifest['previous_release']['release_lock'];self.target=bundle['operation_lock']['release']
        if data_digest(self.target)!=bundle['plan']['target_release_digest'] or data_digest(self.base)!=bundle['plan']['base_release_digest']:
            raise OperatorError('Reference recovery release identities changed')
        self.known={data_digest(lock):lock for lock in [self.base,self.target]}
        self.fresh_database='mp_disposable_r0_r1_restore_'+bundle['plan']['operation_id'].replace('-','')

    def _matches_target(self,target,configuration):
        base=self.manifest['configuration']
        names={base['sites'][0]['database'],self.native.config['sites'][0]['database'],self.fresh_database}
        return (all(target[k]==configuration[k]==base[k] for k in ['deployment_id','project'])
            and len(target['sites'])==len(configuration['sites'])==1
            and target['sites'][0]['site_id']==configuration['sites'][0]['site_id']==base['sites'][0]['site_id']
            and target['sites'][0]['database'] in names and configuration['sites'][0]['database'] in names)

    def _metadata_release(self,configuration,metadata):
        configured=configuration['published_release'];digest=metadata['release_digest']
        if self.purpose=='source_inspection':
            selected=self.known.get(digest)
            if selected is None:raise OperatorError('Failed source is neither checkpoint nor exact approved target metadata')
        else:
            selected=configured
            if digest!=data_digest(selected):raise OperatorError('Restored reference publication differs from reviewed configuration')
            if digest not in self.known:
                expected=copy.deepcopy(self.base)
                expected.update(generation=selected.get('generation'),created_at=selected.get('created_at'))
                if (selected!=expected or configuration['sites'][0]['database']!=self.fresh_database
                        or type(selected['generation']) is not int or selected['generation']<=max(self.base['generation'],self.target['generation'])
                        or selected['created_at']!=self.bundle['plan']['created_at']):
                    raise OperatorError('Fresh reference epoch is not derived from the reviewed checkpoint')
        if metadata['release_generation']!=str(selected['generation']) or metadata['active_inventory_digest']!=selected['core_inventory_digest']:
            raise OperatorError('Reference metadata epoch/inventory differs from known release')
        return selected

    def observer(self,configuration):
        def fresh():
            reader=WorkerPlanningReader(self.native.store,self.native.target_path,self.native.target_path.with_name('worker-target.json'))
            if not self._matches_target(reader.target,configuration):raise OperatorError('Reference recovery observer changed deployment/site/database scope')
            return reader.planning_state()
        return DockerObserver(configuration,external_reader=fresh)

    def run(self,action,operation,directory,**kwargs):
        if self.purpose=='source_inspection' and action!='observe':
            raise OperatorError('Failed-source reference context is read-only and cannot resume dispatch')
        return super().run(action,operation,directory,**kwargs)

    def same_restored_dispatch(self,current,previous,previous_policy,*,checkpoint=False):
        """A new local review may bind current publication revocations/rotation.

        Metadata registrations and every queue/control field must stay exact;
        only the independently owned publication binding may advance.
        """
        policy=self.policy_for(current)
        if (not isinstance(previous_policy,dict) or not isinstance(previous,dict)
                or data_digest(previous_policy)!=previous.get('reference_policy_digest')
                or previous.get('state_digest')!=data_digest({k:v for k,v in previous.items() if k!='state_digest'})):return False
        ignored={'state_digest','reference_policy_digest'}
        if checkpoint:ignored.add('release_digest')
        return ({k:v for k,v in current.items() if k not in ignored}=={k:v for k,v in previous.items() if k not in ignored}
            and {k:v for k,v in policy.items() if k!='publication_digest'}=={k:v for k,v in previous_policy.items() if k!='publication_digest'})
