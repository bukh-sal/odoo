"""Metadata-only lifecycle proposals using the existing frozen plan envelope.

The caller supplies independently observed endpoint state at OS review; an app
cache may prepare the same proposal but cannot authorize it. No runtime control,
native module installation, package-selected URL or new approval channel exists.
"""
import copy
from packaging.version import Version

from .lifecycle_planning import installation_id
from .planning_cli import prepare_document
from .projection import external_observation
from .resolution import PlanningError


def external_selections(bundle):
    wanted={r['plugin_id'] for r in bundle['operation_lock']['targets'] if r['action'] in ('install','upgrade')}
    return [{k:r[k] for k in ['plugin_id','version','digest']} for r in bundle['operation_lock']['release']['plugins']
        if r['plugin_id'] in wanted and r['runtime']=='external_service']


def prepare_external_metadata(document, sites, catalog, *, targets, operation_type,
        external_state, operation_id, created_at, selections=(), feature_states=()):
    if operation_type not in ('install','upgrade','enable','suspend','unregister') or not targets:
        raise PlanningError('Explicit external metadata lifecycle targets required')
    external=external_observation(external_state)
    state=document['state'];old={r['plugin_id']:r for r in state['release_lock']['plugins']}
    if operation_type=='unregister':
        scopes={(r['installation_id'],r['site_id'],r['workspace_id']) for r in targets}
        retiring={(r['installation_id'],r['site_id']) for r in targets}
        if any((r['installation_id'],r['site_id']) in retiring and r['state']=='installed'
                and (r['installation_id'],r['site_id'],r['workspace_id']) not in scopes for r in state['installations']):
            raise PlanningError('Site metadata unregistration requires every retained workspace scope')
        if any((g['installation_id'],s['site_id']) in retiring and g['state']=='approved'
                and (g['installation_id'],s['site_id'],g['workspace_id']) not in scopes for s in sites for g in s['grants']):
            raise PlanningError('Unregistration cannot leave approved grants outside its exact scope map')
    by_site={r['site_id']:r for r in sites};chosen={}
    for pin in selections:
        if not isinstance(pin,dict) or set(pin)!={'plugin_id','version','digest'} or pin['plugin_id'] in chosen:
            raise PlanningError('Exact unique external artifact selection required')
        chosen[pin['plugin_id']]=pin
    selecting=operation_type in ('install','upgrade')
    if set(chosen)!=({r['plugin_id'] for r in targets} if selecting else set()):
        raise PlanningError('External metadata selection must match exact changed targets')
    features=copy.deepcopy(list(feature_states))
    keys=lambda row:(row['installation_id'],row['site_id'],row['workspace_id'])
    if operation_type=='install':
        if (len(features)!=len(targets) or any(set(r)!={'installation_id','site_id','workspace_id','availability'}
                or r['availability'] not in ('enabled','suspended') for r in features)
                or len({keys(r) for r in features})!=len(features) or {keys(r) for r in features}!={keys(r) for r in targets}):
            raise PlanningError('Explicit complete external post-install feature map required')
    elif features:raise PlanningError('Feature post-state map applies only to metadata registration')
    availability={keys(r):r['availability'] for r in features}
    if operation_type=='upgrade':
        availability.update({keys(r):r['feature_state'] for r in state['installations']})
    changes=[];requested={};endpoints=[]
    retiring={(r['installation_id'],r['workspace_id']) for r in targets if r['action']=='unregister'}
    live={(r['installation_id'],r['workspace_id']) for r in state['installations'] if r['state']=='installed'}
    live.update((r['installation_id'],r['workspace_id']) for r in targets if r['action'] in ('install','upgrade'))
    live-=retiring
    for endpoint in external['endpoints']:
        if (endpoint['installation_id'],endpoint['workspace_id']) in live:endpoints.append(endpoint)
    for target in targets:
        if set(target)!={'installation_id','site_id','workspace_id','plugin_id','action'}:
            raise PlanningError('Exact external lifecycle scope required')
        if target['action']!=operation_type:
            raise PlanningError('External target action differs from operation')
        site=by_site.get(target['site_id']);plugin=target['plugin_id']
        if site is None or target['installation_id']!=installation_id(site,plugin):
            raise PlanningError('External target differs from independently derived site installation')
        activating=operation_type=='enable' or availability.get(keys(target))=='enabled'
        workspace=next((r for r in site['workspaces'] if r['workspace_id']==target['workspace_id']),None)
        if workspace is None or activating and workspace['state']!='active':
            raise PlanningError('External activation requires an active observed workspace')
        pin=chosen.get(plugin) or old.get(plugin)
        matches=[r for r in catalog if pin and r['manifest']['plugin']['id']==plugin
            and r['manifest']['plugin']['version']==pin['version'] and r['digest']==pin['digest']]
        if len(matches)!=1 or matches[0]['manifest']['runtime']!={'kind':'external_service'}:
            raise PlanningError('Exact current trusted external metadata package required')
        descriptor=matches[0];manifest=descriptor['manifest']
        if operation_type=='upgrade' and (plugin not in old or Version(pin['version'])<=Version(old[plugin]['version'])):
            raise PlanningError('Metadata upgrade requires a strictly newer package version')
        if any(name.startswith(('backend/','frontend/','migrations/')) for name in descriptor.get('inventory',{})):
            raise PlanningError('Metadata lifecycle cannot import executable plugin code')
        scoped=[r for r in external['endpoints'] if all(r[k]==target[k] for k in ['installation_id','site_id','workspace_id'])
            and r['endpoint_config']==manifest['external_service']['endpoint_config']]
        if len(scoped)!=1 or scoped[0]['expected_image_digest']!=manifest['external_service']['expected_image'].split('@',1)[1]:
            raise PlanningError('Exact independently approved external endpoint/image required')
        endpoint=scoped[0]
        if selecting:
            if endpoint['state']!='enabled':raise PlanningError('Registration requires a current enabled endpoint approval')
            requested[plugin]='=='+pin['version']
        if activating:
            health=external['service_health'].get(target['installation_id']+':'+target['workspace_id'],{})
            if endpoint['state']!='enabled' or health.get('state')!='healthy' or health.get('expected_image_digest')!=endpoint['expected_image_digest']:
                raise PlanningError('External activation requires current healthy approved image')
        if operation_type=='unregister' and endpoint['state']!='revoked':
            raise PlanningError('Revoke independent endpoint credentials before metadata unregistration')
        if activating:
            for request in manifest['permissions']['requests']:
                grant=next((g for g in site['grants'] if g['installation_id']==target['installation_id']
                    and g['workspace_id']==target['workspace_id'] and g['capability']==request['capability']),None)
                if grant is None or grant['state']!='approved':
                    changes.append(dict(plugin_id=plugin,workspace_id=target['workspace_id'],capability=request['capability'],action='grant'))
        if operation_type=='unregister':
            changes.extend(dict(plugin_id=plugin,workspace_id=target['workspace_id'],capability=g['capability'],action='revoke')
                for g in site['grants'] if g['installation_id']==target['installation_id']
                and g['workspace_id']==target['workspace_id'] and g['state']=='approved')
    request=dict(operation_type=operation_type,requested=requested,targets=targets,endpoints=endpoints,
        permission_changes=changes,operation_id=operation_id,created_at=created_at)
    if selecting:request.update(update=sorted(chosen))
    if operation_type=='install':request['feature_states']=features
    if operation_type in ('enable','suspend'):request['bindings']=state.get('bindings',[])
    bundle=prepare_document({**document,'request':request},catalog,retained_trust_for=set(old)-set(chosen))
    # Selecting metadata may advance the release epoch and service choices, but
    # cannot sneak native code, Python, core provenance or other artifact changes.
    release=bundle['operation_lock']['release'];base=state['release_lock']
    for key in set(base)-{'plugins','generation','created_at','service_selection','optional_integrations','frontend_inventory','frontend_inventory_digest'}:
        if release[key]!=base[key]:raise PlanningError('Metadata operation changed the native/Python release')
    expected_frontend=copy.deepcopy(base['frontend_inventory'])
    for plugin in chosen:expected_frontend[plugin]={}
    if release['frontend_inventory']!=expected_frontend:
        raise PlanningError('Metadata operation changed frontend executable bytes')
    actual={r['plugin_id']:r for r in release['plugins']}
    if set(actual)!=set(old)|set(chosen) or any(actual[p]!=r for p,r in old.items() if p not in chosen):
        raise PlanningError('Metadata operation changed an untargeted artifact')
    for plugin,pin in chosen.items():
        if any(actual[plugin][k]!=pin[k] for k in ['plugin_id','version','digest']) or actual[plugin]['runtime']!='external_service':
            raise PlanningError('Solved external artifact differs from exact nomination')
    return bundle
