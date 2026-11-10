"""Optional reviewed reference lifecycle validator, appended by the host child."""
import re
from packaging.version import Version
from modular_platform import durable
from modular_platform.dispatch_lifecycle import DispatchLifecycleError
from modular_platform.plans import data_digest


def _reference_impl(cr,scope):
    """Private OS-selected profile, never a DB flag or general remote allowlist.

    The host verifies catalog/release/publication provenance. This transaction
    checks its exact physical metadata footprint again, including tombstones.
    Supported authority is outbound-only, to the stateless reference worker.
    """
    value=scope.reference
    keys={'profile','site_id','runtime_image','publication_digest','registrations'}
    transition=value.get('worker_transition') if isinstance(value,dict) else None
    transitioning=isinstance(value,dict) and value.get('profile')=='r1-reference-stateless-transition-v1'
    if (not isinstance(value,dict) or set(value)!=(keys|{'worker_transition'} if transitioning else keys)
            or value['profile'] not in {'r1-reference-stateless-v1','r1-reference-stateless-transition-v1'}
            or value['site_id']!=scope.site_id or not isinstance(value['runtime_image'],str)
            or not re.fullmatch(r'modular-document-stats@sha256:[0-9a-f]{64}',value['runtime_image'])
            or not isinstance(value['publication_digest'],str) or not re.fullmatch('sha256:[0-9a-f]{64}',value['publication_digest'])
            or not isinstance(value['registrations'],list) or len(value['registrations'])>256):
        raise DispatchLifecycleError('Exact independently selected reference profile required')
    if transitioning:
        fields={'operation_id','plan_hash','installation_id','base_version','base_artifact_digest','base_manifest_digest','base_image',
                'target_version','target_artifact_digest','target_manifest_digest','target_image','workspaces'}
        if not isinstance(transition,dict) or set(transition)!=fields:
            raise DispatchLifecycleError('Exact private reviewed image transition required')
        try:
            durable._uuid(transition['operation_id']);durable._uuid(transition['installation_id'])
            from packaging.version import Version
            if Version(transition['target_version'])<=Version(transition['base_version']):raise ValueError()
            for key in ('plan_hash','base_artifact_digest','base_manifest_digest','target_artifact_digest','target_manifest_digest'):
                if not re.fullmatch(r'sha256:[0-9a-f]{64}',transition[key]):raise ValueError()
            if (not re.fullmatch(r'modular-document-stats@sha256:[0-9a-f]{64}',transition['base_image'])
                    or transition['target_image']!=value['runtime_image'] or transition['base_image']==transition['target_image']
                    or not isinstance(transition['workspaces'],list) or not transition['workspaces']
                    or transition['workspaces']!=sorted(set(transition['workspaces']))):raise ValueError()
            for workspace in transition['workspaces']:durable._uuid(workspace)
        except (ValueError,TypeError,KeyError):raise DispatchLifecycleError('Invalid private reviewed image transition') from None
    expected=[]
    for row in value['registrations']:
        if (not isinstance(row,dict) or set(row)!={'installation_id','plugin_id','version','artifact_digest','manifest_digest','state','features'}
                or row['plugin_id']!='org.example.document_stats' or row['state'] not in {'installed','removed'}
                or any(not isinstance(row[k],str) or not re.fullmatch('sha256:[0-9a-f]{64}',row[k]) for k in ['artifact_digest','manifest_digest'])
                or not isinstance(row['features'],list) or len(row['features'])>256):
            raise DispatchLifecycleError('Unknown external registration is outside the reference profile')
        durable._uuid(row['installation_id'])
        for feature in row['features']:
            if (not isinstance(feature,dict) or set(feature)!={'workspace_id','feature_state'}
                    or feature['feature_state'] not in {'enabled','suspended'}
                    or row['state']=='removed' and feature['feature_state']!='suspended'):
                raise DispatchLifecycleError('Exact retained reference feature scope required')
            durable._uuid(feature['workspace_id'])
        if len({f['workspace_id'] for f in row['features']})!=len(row['features']):
            raise DispatchLifecycleError('Duplicate reference workspace scope')
        expected.append(row)
    if len({r['installation_id'] for r in expected})!=len(expected):raise DispatchLifecycleError('Duplicate reference installation')
    cr.execute("SELECT id,public_id,plugin_id,version,artifact_digest,state,manifest FROM mp_plugin_installation WHERE runtime<>'native' ORDER BY public_id")
    actual=[];used_transition=False
    for ident,public,plugin,version,digest,state,manifest in cr.fetchall():
        if (not isinstance(manifest,dict) or manifest.get('runtime')!={'kind':'external_service'}
                or not isinstance(manifest.get('external_service'),dict)
                or not re.fullmatch(r'modular-document-stats@sha256:[0-9a-f]{64}',manifest['external_service'].get('expected_image',''))):
            raise DispatchLifecycleError('External image/runtime differs from independently selected reference')
        cr.execute('''SELECT w.public_id,f.availability,f.plugin_id FROM mp_workspace_plugin f JOIN mp_workspace w ON w.id=f.workspace_id
            WHERE f.installation_id=%s ORDER BY w.public_id''',[ident])
        features=cr.fetchall()
        if any(p!=plugin for _,_,p in features):raise DispatchLifecycleError('Reference feature ownership changed')
        if state!='removed' and manifest['external_service']['expected_image']!=value['runtime_image']:
            if (not transitioning or used_transition or state!='installed' or public!=transition['installation_id']
                    or plugin!='org.example.document_stats' or version!=transition['base_version'] or digest!=transition['base_artifact_digest']
                    or data_digest(manifest)!=transition['base_manifest_digest'] or manifest['external_service']['expected_image']!=transition['base_image']
                    or sorted(w for w,_,_ in features)!=transition['workspaces'] or any(a!='suspended' for _,a,_ in features)):
                raise DispatchLifecycleError('External image/runtime differs from independently selected reference')
            used_transition=True
        actual.append(dict(installation_id=public,plugin_id=plugin,version=version,artifact_digest=digest,
            manifest_digest=data_digest(manifest),state=state,features=[dict(workspace_id=w,feature_state=a) for w,a,_ in features]))
    if actual!=sorted(expected,key=lambda r:r['installation_id']):
        raise DispatchLifecycleError('Reference metadata changed after independent observation')
    if transitioning and not used_transition:raise DispatchLifecycleError('Unused image transition proof cannot authorize another profile')
    return data_digest(value)


def reference_policy(cr,scope):
    digest=_reference_impl(cr,scope)
    return {'profile':'r1-reference-stateless-dispatch-v1','digest':digest}
