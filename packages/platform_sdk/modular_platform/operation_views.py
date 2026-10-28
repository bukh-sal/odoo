"""Public proposal/mirror projections. These values never confer OS authority."""
from .contracts import validate_operations_view


def prepared_view(bundle, *, observed_at, stale=False):
    declarations=[]
    for plugin,change in bundle['operation_lock']['declaration_changes'].items():
        previous=change.get('previous_permissions') or {}
        target=change['target_permissions']
        capabilities={name if ':' in name else plugin+':'+name for name in set(target.get('defines',{}))-set(previous.get('defines',{}))}
        capabilities.update(item['capability'] for item in target.get('requests',[]) if item not in previous.get('requests',[]))
        scopes=set(change['target_activation']['scopes'])-set((change.get('previous_activation') or {}).get('scopes',[]))
        declarations.append({'plugin_id':plugin,'added_capabilities':sorted(capabilities),'added_scopes':sorted(scopes)})
    value={'schema_version':1,'kind':'prepared','operation_id':bundle['plan']['operation_id'],'plan_hash':bundle['plan_hash'],
        'plan':bundle['plan'],'targets':bundle['operation_lock']['targets'],'declaration_changes':declarations,
        'native_trusted_code':bundle['display']['native_code_requires_trust'],'restart_required':bundle['display']['restart_required'],
        'feature_suspension_unloads_code':False,'known_unknowns':bundle['display']['known_unknowns'],
        'control_authority':'independent_local_os','observed_at':observed_at,'stale':stale}
    return validate_operations_view(value)


def request_status(bundle, *, actor, dimensions, observed_at, requested=False):
    history=[{'sequence':1,'utc':bundle['plan']['created_at'],'code':'prepared'}]
    if requested:history.append({'sequence':2,'utc':observed_at,'code':'requested'})
    return validate_operations_view({'schema_version':1,'kind':'status','operation_id':bundle['plan']['operation_id'],
        'plan_hash':bundle['plan_hash'],'requested_by':actor,'state':'awaiting_operator_approval','phase':'prepared',
        'source':'application_request','observed_at':observed_at,'stale':False,'approval_expires_at':None,
        'dimensions':dimensions,'history':history,'error_code':None,'control_authority':'independent_local_os'})
