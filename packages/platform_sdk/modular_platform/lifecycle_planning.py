"""Data-only native installation nominations for an already verified image.

New executable bytes need a separately staged image. This path can install
packages present in the operator-pinned image without accepting app-selected
code, Python dependencies, database names or installation identities.
"""
from uuid import UUID, uuid5

from .planning_cli import prepare_document
from .resolution import PlanningError, binding_matches_scope


def installation_id(site, plugin):
    previous = [item for item in site['installations'] if item['plugin_id'] == plugin]
    if len(previous) > 1:
        raise PlanningError('Ambiguous site installation identity')
    return previous[0]['installation_id'] if previous else str(uuid5(UUID(site['site_id']), 'plugin:' + plugin))


def validate_install_targets(document, sites, targets):
    by_site = {site['site_id']: site for site in sites}
    release = {item['plugin_id']: item for item in document['state']['release_lock']['plugins']}
    for target in targets:
        site = by_site.get(target['site_id'])
        if site is None or not any(item['workspace_id'] == target['workspace_id'] and item['state'] == 'active'
                                   for item in site['workspaces']):
            raise PlanningError('Install target requires an independently observed active workspace')
        if target['action'] != 'install' or target['plugin_id'] not in release or release[target['plugin_id']]['runtime'] != 'native':
            raise PlanningError('Current-image installation accepts native install targets only')
        if target['installation_id'] != installation_id(site, target['plugin_id']):
            raise PlanningError('Install target differs from the independently derived site installation identity')
        previous = next((item for item in site['installations'] if item['plugin_id'] == target['plugin_id']), None)
        if previous and previous['metadata_state'] != 'installed':
            raise PlanningError('Existing site installation requires explicit reconciliation before new activation')
        required = set(release[target['plugin_id']]['hard_dependencies'])
        required.update(item['provider'] for item in document['state']['release_lock']['service_selection']
            if item['consumer'] == target['plugin_id'] and not item['optional']
            and binding_matches_scope(item, target['site_id'], target['workspace_id']))
        for plugin in required:
            targeted = any(item['plugin_id'] == plugin and item['site_id'] == target['site_id']
                and item['workspace_id'] == target['workspace_id'] and item['action'] == 'install' for item in targets)
            existing = next((item for item in document['state']['installations'] if item['plugin_id'] == plugin
                and item['site_id'] == target['site_id'] and item['workspace_id'] == target['workspace_id']), None)
            if not targeted and (not existing or existing['state'] != 'installed'
                    or existing['metadata_state'] != 'installed' or existing['feature_state'] != 'enabled'):
                raise PlanningError('Install target omits a required scoped provider/dependency')


def prepare_current_image_install(document, sites, catalog, *, site_id, workspace_ids,
                                  plugin_id, version, artifact_digest, operation_id, created_at):
    release = document['state']['release_lock']
    entries = {item['plugin_id']: item for item in release['plugins']}
    chosen = entries.get(plugin_id)
    if chosen is None or (chosen['version'], chosen['digest']) != (version, artifact_digest):
        raise PlanningError('Requested artifact requires a separately staged and verified release image')
    if not workspace_ids or len(workspace_ids) != len(set(workspace_ids)):
        raise PlanningError('Explicit unique workspace targets required')
    site = next((item for item in sites if item['site_id'] == site_id), None)
    if site is None:
        raise PlanningError('Install site is outside the observed deployment')
    existing = {(item['plugin_id'], item['workspace_id']): item for item in document['state']['installations']
                if item['site_id'] == site_id}
    targets = []
    for workspace in sorted(workspace_ids):
        closure = {plugin_id}
        while True:
            dependencies = {dependency for plugin in closure for dependency in entries[plugin]['hard_dependencies']}
            dependencies.update(item['provider'] for item in release['service_selection']
                if item['consumer'] in closure and not item['optional'] and binding_matches_scope(item, site_id, workspace))
            if dependencies <= closure:
                break
            closure.update(dependencies)
        for plugin in sorted(closure):
            prior = existing.get((plugin, workspace))
            if prior and prior['state'] == 'installed':
                if plugin == plugin_id:
                    raise PlanningError('Requested plugin already installed at this workspace')
                if prior['feature_state'] != 'enabled' or prior['metadata_state'] != 'installed':
                    raise PlanningError('Required provider must be explicitly enabled before installation')
                continue
            targets.append({'installation_id': installation_id(site, plugin), 'site_id': site_id,
                'workspace_id': workspace, 'plugin_id': plugin, 'action': 'install'})
    validate_install_targets(document, sites, targets)
    request = {'operation_type': 'install', 'requested': {}, 'targets': targets,
               'operation_id': operation_id, 'created_at': created_at}
    return prepare_document({**document, 'request': request}, catalog)
