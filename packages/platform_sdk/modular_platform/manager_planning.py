"""Data-only manager nominations; independent staging remains authoritative.

The application sees only a sanitized candidate preview. It cannot select an
image, command, path or installation ID. The local validator reconstructs the
result against its private StageStore before registration, approval and apply.
"""
from packaging.version import Version
import copy

from .contracts import validate
from .lifecycle_planning import installation_id, prepare_current_image_install
from .plans import data_digest
from .projection import runtime_inputs
from .release_staging import prepare_staged_plan
from .resolution import PlanningError, binding_matches_scope, resolve_release, dependent_closure


def candidate_preview(descriptor, runtime, base_image_id):
    keys = {'stage_digest', 'base_image_id', 'target_image_id', 'inventory_digest', 'runtime_digest'}
    import re
    if (not isinstance(descriptor, dict) or set(descriptor) != keys
            or any(not isinstance(value, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', value)
                   for value in descriptor.values())
            or descriptor['base_image_id'] != base_image_id
            or descriptor['inventory_digest'] != runtime.get('inventory_digest')
            or descriptor['runtime_digest'] != data_digest(runtime)):
        raise PlanningError('Staged preview is stale or differs from its exact runtime')
    return {'descriptor': dict(descriptor), 'runtime': runtime}


def prepare_manager_removal(document,sites,catalog,base_runtime,staged,nomination,*,operation_id,created_at):
    validate('operations-request',nomination)
    if (nomination['operation']!='prepare' or nomination['operation_type']!='remove'
            or nomination['workspace_ids'] or nomination['site_id'] not in document['state']['site_ids']):
        raise PlanningError('Source removal requires a site-wide current-site nomination')
    artifact=base_runtime['inventory'].get('artifacts',{}).get(nomination['plugin_id'])
    if not artifact or artifact['digest']!=nomination['artifact_digest']:
        raise PlanningError('Select the exact package currently present in this runtime for source removal')
    if not staged or set(staged)!={'descriptor','runtime'}:
        raise PlanningError('Local operator must stage and publish the exact source-removal image first')
    candidate_preview(staged['descriptor'],staged['runtime'],document['state']['image_id'])
    removed=set(base_runtime['inventory'].get('artifacts',{}))-set(staged['runtime']['inventory'].get('artifacts',{}))
    if nomination['plugin_id'] not in removed:
        raise PlanningError('The independently staged image does not remove the nominated package')
    if len(removed)>1 and not nomination['cascade']:
        raise PlanningError('Explicit dependent cascade consent required for multiple source removals')
    external=[p for p in document['state']['release_lock']['plugins'] if p['runtime']=='external_service']
    selected,_,_=runtime_inputs(base_runtime,catalog,external_plugins=external)
    descriptors=copy.deepcopy(selected)
    for item in descriptors:
        item['required_providers']=[row['provider'] for row in document['state']['release_lock']['service_selection']
            if row['consumer']==item['plugin_id'] and not row['optional']]
    allowed=set(dependent_closure(descriptors,[nomination['plugin_id']],cascade=True))
    if not removed<=allowed:
        raise PlanningError('Removal image includes packages outside the nominated dependent closure')
    from .artifact_removal import removal_targets
    targets=removal_targets(document,sites,sorted(removed))
    return prepare_staged_plan(document,sites,catalog,staged['runtime'],staged['descriptor'],targets=targets,
        operation_type='remove',operation_id=operation_id,created_at=created_at,base_runtime=base_runtime)


def manager_runtime(document, catalog, nomination):
    """Choose behavior from the exact catalog pin, never a browser runtime flag."""
    validate('operations-request',nomination)
    if nomination['operation_type'] in ('install','upgrade'):
        matches=[r for r in catalog if r['manifest']['plugin']['id']==nomination['plugin_id']
                 and r['manifest']['plugin']['version']==nomination['artifact_version'] and r['digest']==nomination['artifact_digest']]
    else:
        matches=[r for r in document['state']['release_lock']['plugins'] if r['plugin_id']==nomination['plugin_id']]
    if len(matches)!=1:raise PlanningError('Select one exact current curated artifact or installed plugin')
    chosen=matches[0]
    return chosen['manifest']['runtime']['kind'] if 'manifest' in chosen else chosen['runtime']


def prepare_manager_external(document, sites, catalog, external_state, nomination, *, operation_id, created_at):
    """Metadata nominations only; OS review reconstructs endpoint authority anew."""
    from .external_planning import prepare_external_metadata
    validate('operations-request',nomination)
    action=nomination['operation_type'];plugin=nomination['plugin_id'];site_id=nomination['site_id']
    if nomination['operation']!='prepare' or action not in ('install','upgrade','enable','suspend','unregister'):
        raise PlanningError('External metadata cannot use native uninstall or source removal')
    if manager_runtime(document,catalog,nomination)!='external_service':raise PlanningError('Metadata nomination requires an external service')
    site=next((s for s in sites if s['site_id']==site_id),None)
    if site is None or site_id not in document['state']['site_ids']:raise PlanningError('Current site required')
    current=[r for r in document['state']['installations'] if r['site_id']==site_id and r['plugin_id']==plugin and r['state']=='installed']
    requested=set(nomination['workspace_ids']);retained={r['workspace_id'] for r in current}
    active={w['workspace_id'] for w in site['workspaces'] if w['state']=='active'}
    if action in ('upgrade','unregister'):
        if not current or requested-retained:raise PlanningError('Metadata operation requires existing site scopes')
        workspaces=retained  # One metadata identity is shared by every retained scope.
    else:
        workspaces=requested
        if not workspaces or (action in ('install','enable') and not workspaces<=active):
            raise PlanningError('Explicit active workspace targets required')
        if action in ('enable','suspend') and not workspaces<=retained:raise PlanningError('Metadata feature scope is not installed')
    targets=[dict(installation_id=installation_id(site,plugin),site_id=site_id,workspace_id=w,plugin_id=plugin,action=action) for w in sorted(workspaces)]
    selections=[dict(plugin_id=plugin,version=nomination['artifact_version'],digest=nomination['artifact_digest'])] if action in ('install','upgrade') else []
    # The existing frozen nomination has no activation field. Registration is
    # explicitly suspended; a separate reviewed enable rechecks live health/keys.
    features=[{k:t[k] for k in ('installation_id','site_id','workspace_id')}|dict(availability='suspended') for t in targets] if action=='install' else []
    return prepare_external_metadata(document,sites,catalog,targets=targets,operation_type=action,
        external_state=external_state,selections=selections,feature_states=features,operation_id=operation_id,created_at=created_at)


def prepare_manager_native(document, sites, catalog, base_runtime, staged, nomination, *, operation_id, created_at):
    validate('operations-request', nomination)
    action = nomination['operation_type']
    if nomination['operation'] != 'prepare' or action not in ('install', 'upgrade'):
        raise PlanningError('Native manager preparation requires install or upgrade')
    current = next((r for r in document['state']['release_lock']['plugins'] if r['plugin_id'] == nomination['plugin_id']), None)
    if action == 'install' and current and (current['version'], current['digest']) == (nomination['artifact_version'], nomination['artifact_digest']):
        bundle = prepare_current_image_install(document, sites, catalog, site_id=nomination['site_id'],
            workspace_ids=nomination['workspace_ids'], plugin_id=nomination['plugin_id'], version=nomination['artifact_version'],
            artifact_digest=nomination['artifact_digest'], operation_id=operation_id, created_at=created_at)
        if not nomination['cascade'] and any(t['plugin_id'] != nomination['plugin_id'] for t in bundle['operation_lock']['targets']):
            raise PlanningError('Explicit dependent cascade consent required for native installation')
        return bundle
    if not staged or set(staged) != {'descriptor', 'runtime'}:
        raise PlanningError('Local operator must stage and publish the selected native release first')
    candidate_preview(staged['descriptor'], staged['runtime'], document['state']['image_id'])
    external=[p for p in document['state']['release_lock']['plugins'] if p['runtime']=='external_service']
    selected, environment, _ = runtime_inputs(staged['runtime'], catalog,external_plugins=external)
    entries = {item['manifest']['plugin']['id']: item for item in selected}
    plugin = nomination['plugin_id']; chosen = entries.get(plugin)
    if chosen is None or (chosen['manifest']['plugin']['version'], chosen['digest']) != (
            nomination['artifact_version'], nomination['artifact_digest']):
        raise PlanningError('Selected artifact is absent from the operator-staged image')
    if chosen['manifest']['runtime']['kind']!='native':
        raise PlanningError('Native manager cannot nominate external metadata lifecycle changes')
    site_id = nomination['site_id']; workspaces = nomination['workspace_ids']
    site = next((item for item in sites if item['site_id'] == site_id), None)
    if not workspaces or site is None or not set(workspaces) <= {
            item['workspace_id'] for item in site['workspaces'] if item['state'] == 'active'}:
        raise PlanningError('Explicit active workspace targets are required')
    current = document['state']['release_lock']
    old = {item['plugin_id']: item for item in current['plugins']}
    installed = {(item['site_id'], item['workspace_id'], item['plugin_id']): item
                 for item in document['state']['installations']}
    if action=='install' and any(i['plugin_id']==plugin and i['metadata_state']=='removed' for i in site['installations']):
        targets=[dict(installation_id=installation_id(site,plugin),site_id=site_id,workspace_id=w,plugin_id=plugin,action='install') for w in workspaces]
        bundle=prepare_staged_plan(document,sites,catalog,staged['runtime'],staged['descriptor'],targets=targets,
            operation_type='install',operation_id=operation_id,created_at=created_at,base_runtime=base_runtime)
        if not nomination['cascade'] and any(t['plugin_id']!=plugin for t in bundle['operation_lock']['targets']):
            raise PlanningError('Explicit dependent cascade consent required for native reinstall')
        return bundle
    changed = {name for name, item in entries.items() if name not in old or old[name]['digest'] != item['digest']}
    if action == 'upgrade' and (plugin not in changed or plugin not in old
            or Version(nomination['artifact_version']) <= Version(old[plugin]['version'])):
        raise PlanningError('Upgrade requires a strictly newer staged package version')
    for workspace in workspaces:
        previous = installed.get((site_id, workspace, plugin))
        if action == 'install' and previous or action == 'upgrade' and not previous:
            raise PlanningError('Install requires an absent scope; upgrade requires an installed scope')

    choices = {(item['consumer'], item['alias'], target_site, workspace): item['provider']
               for item in current['service_selection'] for target_site, workspace in item.get('scopes', [])}
    solution = resolve_release(selected, staged['runtime']['python_metadata'], environment,
        {name: '==' + item['manifest']['plugin']['version'] for name, item in entries.items()},
        scoped_provider_choices=choices,
        core_python=[item['name'] + '==' + item['version'] for item in staged['runtime']['python_metadata']])
    targets = {}
    def add(target_site, workspace, name, target_action):
        actual_site = next((item for item in sites if item['site_id'] == target_site), None)
        if actual_site is None or name not in entries:
            raise PlanningError('Candidate omits a required site or dependency')
        targets[target_site, workspace, name] = {'installation_id': installation_id(actual_site, name),
            'site_id': target_site, 'workspace_id': workspace, 'plugin_id': name, 'action': target_action}
    # Native code is shared: every existing scope of a changed artifact is an
    # explicit upgrade target, including suspended scopes. Availability stays put.
    for (target_site, workspace, name), previous in installed.items():
        if name in changed:
            add(target_site, workspace, name, 'upgrade')
    for workspace in workspaces:
        add(site_id, workspace, plugin, action)
    while True:
        before = len(targets)
        for target in list(targets.values()):
            name, target_site, workspace = (target[key] for key in ('plugin_id', 'site_id', 'workspace_id'))
            required = set(entries[name]['manifest']['dependencies']['plugins'])
            required.update(item['provider'] for item in solution['bindings']
                if item['consumer'] == name and not item['optional'] and binding_matches_scope(item, target_site, workspace))
            for dependency in required:
                previous = installed.get((target_site, workspace, dependency))
                if previous is None:
                    add(target_site, workspace, dependency, 'install')
        if len(targets) == before:
            break
    if not nomination['cascade'] and any(item['plugin_id'] != plugin for item in targets.values()):
        raise PlanningError('Explicit dependent changes consent is required for the proposed transitive targets')
    return prepare_staged_plan(document, sites, catalog, staged['runtime'], staged['descriptor'],
        targets=sorted(targets.values(), key=lambda item: (item['site_id'], item['workspace_id'], item['plugin_id'])),
        operation_type=action, operation_id=operation_id, created_at=created_at, base_runtime=base_runtime)
