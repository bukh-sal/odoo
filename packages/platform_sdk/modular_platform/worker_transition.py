"""Private stored-operation proof for an inert reference image upgrade."""
from packaging.version import Version
from .operator_os import OperatorError
from .plans import data_digest

def reviewed_worker_transition(native,operation,base,configuration,row,metadata,catalog,reader,observed,*,recovery=False):
    """Caller is an OS adapter; serialized proposals never select this path."""
    if not isinstance(operation,str):raise OperatorError('Reviewed worker-image upgrade context required')
    bundle=native.store.bundle(operation);plan=bundle['plan'];lock=bundle['operation_lock']
    native.store._authorize_plan(plan)
    allowed={'recovery_required','revoked','running'} if recovery else {'approved','running'}
    if (native.store.status(operation)['state'] not in allowed or plan['operation_id']!=operation
            or lock['operation_id']!=operation or plan['operation_type']!='upgrade'
            or plan['deployment_id']!=configuration['deployment_id']
            or len(configuration['sites'])!=1 or plan['site_ids']!=[configuration['sites'][0]['site_id']]
            or data_digest(base)!=plan['base_release_digest']
            or data_digest(lock['release'])!=plan['target_release_digest']
            or not plan['artifacts'] or any(a['runtime']!='external_service' for a in plan['artifacts'])):
        raise OperatorError('Exact approved reference upgrade/base/target required')
    plugin='org.example.document_stats';old=row['manifest'];image=reader.config['runtime']['image']
    before=next((p for p in base['plugins'] if p['plugin_id']==plugin),None)
    target=next((p for p in lock['release']['plugins'] if p['plugin_id']==plugin),None)
    candidates=[d for d in catalog if target and d['digest']==target['digest'] and d['manifest']['plugin']['id']==plugin]
    if (row['plugin_id']!=plugin or row['metadata_state']!='installed' or before is None or target is None or len(candidates)!=1
            or any(before[k]!=row[v] for k,v in [('version','version'),('digest','digest')])
            or before['manifest_digest']!=data_digest(old) or target['runtime']!='external_service'):
        raise OperatorError('Transition old registration must match reviewed base')
    new=candidates[0]['manifest'];oldspec=old['external_service'];newspec=new['external_service']
    if (new['runtime']!={'kind':'external_service'} or Version(target['version'])<=Version(before['version'])
            or new['plugin']['version']!=target['version'] or data_digest(new)!=target['manifest_digest']
            or newspec['expected_image']!=image or image==oldspec['expected_image']
            or {k:v for k,v in oldspec.items() if k!='expected_image'}!={k:v for k,v in newspec.items() if k!='expected_image'}
            or any(p.startswith(('backend/','frontend/','migrations/')) for p in candidates[0].get('inventory',{}))):
        raise OperatorError('Transition needs a distinct compatible reference image target')
    features=[f for f in metadata['features'] if f['installation_id']==row['installation_id']]
    workspaces=sorted(f['workspace_id'] for f in features)
    targets=[t for t in lock['targets'] if t['installation_id']==row['installation_id']]
    if (not features or len(set(workspaces))!=len(workspaces) or any(f['feature_state']!='suspended' or f['plugin_id']!=plugin for f in features)
            or len(targets)!=len(features) or sorted(t['workspace_id'] for t in targets)!=workspaces
            or any(t!={'installation_id':row['installation_id'],'site_id':metadata['site_id'],'workspace_id':t['workspace_id'],'plugin_id':plugin,'action':'upgrade'} for t in targets)
            or len(lock['targets'])!=len(targets)):
        raise OperatorError('Every reviewed provider scope must remain suspended during image transition')
    for workspace in workspaces:
        endpoints=[e for e in observed['endpoints'] if e['installation_id']==row['installation_id'] and e['workspace_id']==workspace]
        reviewed=[e for e in lock['endpoints'] if e['installation_id']==row['installation_id'] and e['workspace_id']==workspace]
        if len(endpoints)!=1 or len(reviewed)!=1:raise OperatorError('Exact scoped reviewed transition endpoint required')
        endpoint=endpoints[0];wanted=reviewed[0]
        if (endpoint['site_id']!=metadata['site_id'] or endpoint['endpoint_config']!=newspec['endpoint_config']
                or endpoint['expected_image_digest']!=image.split('@',1)[1]
                or wanted['expected_image_digest']!=endpoint['expected_image_digest']):
            raise OperatorError('Transition endpoint differs from independently selected target image')
        if recovery:
            # Revocations/rotation are current OS authority, never restored.
            stable={'installation_id','workspace_id','site_id','endpoint_config','destination','expected_image_digest','api_version','allowed_methods'}
            if any(endpoint[k]!=wanted[k] for k in stable) or endpoint['generation']<wanted['generation']:
                raise OperatorError('Recovery transition changed reviewed destination/scope/image')
        else:
            health=observed['service_health'].get(row['installation_id']+':'+workspace,{})
            if (endpoint!=wanted or endpoint['state']!='enabled' or health.get('state')!='healthy'
                    or health.get('expected_image_digest')!=endpoint['expected_image_digest']):
                raise OperatorError('Upgrade requires the exact freshly healthy approved target endpoint')
    return dict(operation_id=operation,plan_hash=bundle['plan_hash'],installation_id=row['installation_id'],
        base_version=row['version'],base_artifact_digest=row['digest'],base_manifest_digest=data_digest(old),base_image=oldspec['expected_image'],
        target_version=target['version'],target_artifact_digest=target['digest'],target_manifest_digest=data_digest(new),target_image=image,workspaces=workspaces)
