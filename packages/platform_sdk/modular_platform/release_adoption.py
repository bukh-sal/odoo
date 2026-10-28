"""Pin an already published, independently completed release without mutation."""
import copy
from datetime import datetime,timezone
import os
from pathlib import Path

from .catalog import Catalog
from .contracts import load_json,plan_hash
from .deployment import DockerObserver
from .operator_os import OperatorError,OperationLocks,protect_directory,current_identity
from .operator_store import _write_new
from .plans import data_digest,_display


def adopt_release(store,target_path,catalog_root,validator,operation):
    path=Path(target_path);store._regular(path);base=load_json(path.read_bytes())
    with OperationLocks(store.root/'locks',base['deployment_id'],[site['site_id'] for site in base['sites']]):
        if load_json(path.read_bytes())!=base:raise OperatorError('Deployment configuration changed before adoption')
        store._authorize_plan({'deployment_id':base['deployment_id'],'site_ids':[site['site_id'] for site in base['sites']],
            'policy_version':base['policy_version'],'operator_authorization_generation':base['operator_authorization_generation']})
        status=store.status(operation);bundle=store.bundle(operation);plan=bundle['plan'];lock=bundle['operation_lock']['release']
        if (status['state']!='completed' or plan['deployment_id']!=base['deployment_id']
                or plan['site_ids']!=sorted(site['site_id'] for site in base['sites'])
                or lock['generation']!=base['generation'] or lock['created_at']!=base['release_created_at']):
            raise OperatorError('Adoption requires the exact current independently completed publication')
        if (plan_hash(plan)!=bundle['plan_hash'] or data_digest(bundle['operation_lock'])!=plan['dependency_lock_digest']
                or data_digest(lock)!=plan['target_release_digest'] or bundle['display']!=_display(plan,bundle['operation_lock'])):
            raise OperatorError('Independent completed publication preimage mismatch')
        staged=bundle['operation_lock'].get('staged_image')
        if staged:approved_image=staged['target_image_id']
        else:
            checkpoint=store.root/'checkpoints'/operation/'manifest.json';store._regular(checkpoint)
            approved_image=load_json(checkpoint.read_bytes())['configuration']['image_id']
        if base['image_id']!=approved_image:raise OperatorError('Current image differs from completed publication')
        target=copy.deepcopy(base);target['published_release']=copy.deepcopy(lock)
        if 'published_release' in base and base!=target:raise OperatorError('Published lock is already pinned differently')
        observer=DockerObserver(base);observation=observer.read()
        snapshot=Catalog(catalog_root,validator,readonly=True).snapshot()
        state=DockerObserver(target).state(observation,snapshot)['state']
        result={'state':'already_pinned' if base==target else 'adopted','operation_id':operation,
            'release_digest':state['release_digest'],'generation':state['generation'],'image_id':state['image_id'],
            'catalog_validation_digest':state['catalog_validation_digest'],'database_or_runtime_changed':False}
        if base==target:return result
        directory=protect_directory(store.root/'release-adoptions'/base['deployment_id'])
        record=directory/(str(base['generation'])+'-'+state['release_digest'][7:]+'.json')
        if record.exists():raise OperatorError('Previous adoption attempt needs reconciliation; no automatic rewrite')
        _write_new(record,{'schema_version':1,'operation_id':operation,'operator_id':current_identity(),
            'utc':datetime.now(timezone.utc).isoformat(),'previous_configuration':base,'configuration':target,
            'observed_digest':data_digest(observation),'result':result})
        temporary=path.with_name(path.name+'.adopt-'+state['release_digest'][7:]+'.tmp')
        _write_new(temporary,target);os.replace(temporary,path)
        return result
