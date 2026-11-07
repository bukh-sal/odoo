"""Independent reviewed native recurrence maintenance; no app-selected policy."""
import copy
from pathlib import Path
import re

from .dispatch_operator import DispatchMaintenance
from .operator_os import OperatorError
from .plans import data_digest
from .worker_operator import private_json


PROFILE='r1-native-recurring-dispatch-v1'


def selected(native):
    site=native.config['sites'][0]
    directory=native.store.root/'job-controls'/'fleets'/native.config['deployment_id']/site['site_id']
    path=directory/'desired.json'
    if not path.exists():return None
    desired=private_json(path)
    if desired.get('recurrence_policy') is None:return None
    approval=desired.get('approval')
    if not isinstance(approval,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',approval):
        raise OperatorError('Exact independently reviewed recurrence role required')
    review=private_json(directory/(approval[7:]+'.review.json'))
    if (data_digest(review)!=approval or review['pins']!=desired['pins']
            or review.get('recurrence_policy')!=desired['recurrence_policy']
            or desired['pins']['target_digest']!=data_digest(native.config)
            or desired['state']!='paused'):
        raise OperatorError('Pause the exact reviewed recurrence role on the current target before maintenance')
    return NativeRecurrenceMaintenance(native,desired['recurrence_policy'],role_approval=approval)


class NativeRecurrenceMaintenance(DispatchMaintenance):
    def __init__(self,native,policy,*,role_approval=None,schedule_origin=None):
        super().__init__(native)
        if (not isinstance(policy,dict) or policy.get('protocol')!=1
                or policy.get('kind')!='native-recurring-credentials-v1'
                or policy.get('site_id')!=native.config['sites'][0]['site_id']):
            raise OperatorError('Known independently reviewed native recurrence policy required')
        self.policy=copy.deepcopy(policy)
        self.role_approval=role_approval
        self.schedule_origin=schedule_origin

    def run(self,action,operation,directory,**kwargs):
        if 'reference' in kwargs or 'recurrence' in kwargs:
            raise OperatorError('Recurrence maintenance policy cannot originate in a caller proposal')
        return super().run(action,operation,directory,**kwargs,recurrence=self.policy)

    def require_profile(self,snapshot,*,closed=False):
        if (not isinstance(snapshot,dict) or snapshot.get('profile')!=PROFILE
                or snapshot.get('recurrence_policy_digest')!=data_digest(self.policy)
                or snapshot.get('state_digest')!=data_digest({key:value for key,value in snapshot.items() if key!='state_digest'})
                or any(snapshot.get(key)!=0 for key in ('external_installations','api_keys','uncertain_jobs'))
                or type(snapshot.get('active_credentials')) is not int
                or not 0<=snapshot['active_credentials']<=len(self.policy['credentials'])
                or closed and (not snapshot.get('control') or snapshot['control']['state'] not in {'paused','restoring'})):
            raise OperatorError('Exact reconciled native recurrence profile required; unknown authority or effects keep dispatch fenced')
        return snapshot

    def policy_for(self,snapshot):
        self.require_profile(snapshot)
        return copy.deepcopy(self.policy)

    def reconcile_jobs(self,operation,directory,**kwargs):
        result=super().reconcile_jobs(operation,directory,**kwargs)
        config=kwargs.get('configuration') or self.native.config
        destination=Path(directory)/'schedules.json'
        if destination.exists():raise OperatorError('Recurring release reconciliation already attempted')
        source=Path(__file__).with_name('recurrence_reconcile.py').read_text(encoding='utf8')
        request=dict(database=config['sites'][0]['database'],site_id=config['sites'][0]['site_id'],
            inventory_digest=kwargs['inventory_digest'],release_digest=kwargs['release_digest'],
            previous_release=self.schedule_origin or kwargs['previous_release'])
        import json
        from .operator_store import _write_new
        arguments,child=self.native._child(operation,self._suffix('recurrence-reconcile',kwargs.get('review_id')),image_id=config['image_id'])
        arguments.insert(2,'-i')
        self.native._private_command(arguments+['-c',source],Path(directory)/'schedules.stdout',input=json.dumps(request).encode(),timeout=120)
        from .contracts import load_json
        observed=load_json((Path(directory)/'schedules.stdout').read_bytes())
        if (observed.get('event')!='recurrence_reconciled' or observed.get('release_digest')!=request['release_digest']
                or observed.get('dispatch_enabled') is not False):
            raise OperatorError('Exact closed recurring reconciliation required')
        _write_new(destination,dict(child=child,**observed))
        return result|dict(recurring_schedules=observed['states'])
