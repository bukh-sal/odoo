"""Data-only manager nominations; independent staging remains authoritative.

The application sees only a sanitized candidate preview. It cannot select an
image, command, path or installation ID. The local validator reconstructs the
result against its private StageStore before registration, approval and apply.
"""
from packaging.version import Version

from .contracts import validate
from .lifecycle_planning import installation_id
from .plans import data_digest
from .projection import runtime_inputs
from .release_staging import prepare_staged_plan
from .resolution import PlanningError, binding_matches_scope, resolve_release


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


def prepare_manager_native(document, sites, catalog, base_runtime, staged, nomination, *, operation_id, created_at):
    validate('operations-request', nomination)
    action = nomination['operation_type']
    if nomination['operation'] != 'prepare' or action not in ('install', 'upgrade'):
        raise PlanningError('Native manager preparation requires install or upgrade')
    if not staged or set(staged) != {'descriptor', 'runtime'}:
        raise PlanningError('Local operator must stage and publish the selected native release first')
    candidate_preview(staged['descriptor'], staged['runtime'], document['state']['image_id'])
    selected, environment, _ = runtime_inputs(staged['runtime'], catalog)
    entries = {item['manifest']['plugin']['id']: item for item in selected}
    plugin = nomination['plugin_id']; chosen = entries.get(plugin)
    if chosen is None or (chosen['manifest']['plugin']['version'], chosen['digest']) != (
            nomination['artifact_version'], nomination['artifact_digest']):
        raise PlanningError('Selected artifact is absent from the operator-staged image')
    site_id = nomination['site_id']; workspaces = nomination['workspace_ids']
    site = next((item for item in sites if item['site_id'] == site_id), None)
    if not workspaces or site is None or not set(workspaces) <= {
            item['workspace_id'] for item in site['workspaces'] if item['state'] == 'active'}:
        raise PlanningError('Explicit active workspace targets are required')
    current = document['state']['release_lock']
    old = {item['plugin_id']: item for item in current['plugins']}
    installed = {(item['site_id'], item['workspace_id'], item['plugin_id']): item
                 for item in document['state']['installations']}
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
