"""Data-only local plan preparation shared by future UI request adaptation."""
from __future__ import annotations

import copy
from uuid import UUID, uuid5
from packaging.utils import canonicalize_name
from packaging.version import Version
from .contracts import api_range

from .plans import check_bundle, data_digest, prepare_plan, release_lock, scoped_installation_key
from .resolution import PlanningError, resolve_release, binding_matches_scope


def scoped_bindings(solution, installations, previous):
    """Materialize explicit scoped aliases with stable IDs/generations."""
    by_scope = {(item['site_id'], item['workspace_id'], item['plugin_id']): item for item in installations}
    old = {(item['consumer_installation_id'], item['workspace_id'], item['alias']): item for item in previous}
    bindings = []
    for installation in sorted(installations, key=lambda item: scoped_installation_key(item)):
        for selected in solution['bindings']:
            if selected['consumer'] != installation['plugin_id']:
                continue
            if not binding_matches_scope(selected, installation['site_id'], installation['workspace_id']):
                continue
            provider = by_scope.get((installation['site_id'], installation['workspace_id'], selected['provider']))
            if not provider:
                if selected['optional']:
                    continue
                raise PlanningError('Required provider has no installation at the consumer scope')
            prior = old.get((installation['installation_id'], installation['workspace_id'], selected['alias']))
            binding = {'schema_version': 1,
                'binding_id': prior['binding_id'] if prior else str(uuid5(UUID(installation['installation_id']), 'service:' + installation['site_id'] + ':' + installation['workspace_id'] + ':' + selected['alias'])),
                'site_id': installation['site_id'], 'workspace_id': installation['workspace_id'],
                'consumer_installation_id': installation['installation_id'], 'alias': selected['alias'],
                'service_id': selected['service_id'], 'contract_major': selected['contract_major'],
                'api_version': selected['api_version'], 'provider_plugin_id': selected['provider'],
                'provider_installation_id': provider['installation_id'],
                'generation': prior['generation'] if prior else 1, 'optional': selected['optional']}
            if prior and binding != prior:
                binding['generation'] += 1
            bindings.append(binding)
    return bindings


def prepare_document(document, catalog):
    required = {'state', 'environment', 'provenance', 'python_metadata', 'request'}
    if not isinstance(document, dict) or set(document) != required:
        raise PlanningError('Plan input requires exact state/environment/provenance/Python/request sections')
    document = copy.deepcopy(document)
    request, state = document['request'], document['state']
    allowed = {'operation_type', 'requested', 'targets', 'update', 'provider_choices', 'core_python',
               'site_requirements', 'bindings', 'endpoints', 'permission_changes', 'trust_changes',
               'operation_id', 'created_at', 'backup_policy'}
    if not isinstance(request, dict) or not {'operation_type', 'requested', 'targets'} <= request.keys() or not request.keys() <= allowed:
        raise PlanningError('Unknown or missing operation request fields')
    locked = {'plugin:' + item['plugin_id']: {'version': item['version'], 'digest': item['digest']} for item in state['release_lock']['plugins']}
    locked.update({'python:' + canonicalize_name(item['name']): {'version': item['version'], 'digest': item['digest']} for item in state['release_lock']['python_solution']})
    # Removal changes executable inventory only after native uninstall/unregister.
    # The pure solver still checks every surviving root and dependency.
    removed = {item['plugin_id'] for item in request['targets'] if item['action'] == 'remove'}
    for plugin in removed:
        locked.pop('plugin:' + plugin, None)
    snapshot = [item for item in catalog if item['manifest']['plugin']['id'] not in removed]
    choices, scoped_choices = {}, {}
    for item in request.get('provider_choices', []):
        if set(item) not in ({'consumer', 'alias', 'provider'}, {'consumer', 'alias', 'provider', 'site_id', 'workspace_id'}):
            raise PlanningError('Provider choices require unique consumer-local aliases')
        if 'site_id' in item:
            key = item['consumer'], item['alias'], item['site_id'], item['workspace_id']
            if key in scoped_choices:
                raise PlanningError('Duplicate scoped provider choice')
            scoped_choices[key] = item['provider']
        else:
            key = item['consumer'], item['alias']
            if key in choices:
                raise PlanningError('Duplicate provider choice')
            choices[key] = item['provider']
    for item in state['release_lock'].get('service_selection', []):
        if item.get('scopes'):
            for site_id, workspace_id in item['scopes']:
                scoped_choices.setdefault((item['consumer'], item['alias'], site_id, workspace_id), item['provider'])
        elif not any(key[:2] == (item['consumer'], item['alias']) for key in choices):
            choices.setdefault((item['consumer'], item['alias']), item['provider'])
    resolved = resolve_release(snapshot, document['python_metadata'], document['environment'], request['requested'],
        locked=locked, update=request.get('update', []), provider_choices=choices, scoped_provider_choices=scoped_choices,
        core_python=request.get('core_python', []), site_requirements=request.get('site_requirements'))
    if request['operation_type'] in ('install', 'upgrade'):
        # An install creates concrete workspace bindings. Bind those provider
        # selections into the release BEFORE hashing it, so observing the newly
        # installed metadata reconstructs the exact same release lock.
        scopes = {(item['plugin_id'], item['site_id'], item['workspace_id']) for item in state['installations']}
        scopes.update((item['plugin_id'], item['site_id'], item['workspace_id']) for item in request['targets'])
        added = False
        for selected in resolved['bindings']:
            for plugin, site, workspace in scopes:
                key = plugin, selected['alias'], site, workspace
                if plugin == selected['consumer'] and binding_matches_scope(selected, site, workspace) and key not in scoped_choices:
                    scoped_choices[key] = selected['provider']
                    added = True
        manifests={item['manifest']['plugin']['id']:item['manifest'] for item in resolved['plugins']}
        for plugin,site,workspace in scopes:
            for requirement in manifests[plugin]['services']['requires']:
                key=plugin,requirement['alias'],site,workspace
                if key in scoped_choices:continue
                eligible={ident for ident,manifest in manifests.items() if any(
                    provided['id']==requirement['id'] and int(provided['api_version'].split('.')[0])==requirement['contract_major']
                    and Version(provided['api_version']) in api_range(requirement['version'],requirement['contract_major'])
                    for provided in manifest['services']['provides'])}
                if len(eligible)>1:
                    raise PlanningError('Explicit provider binding required for a new workspace alias: '+plugin+':'+requirement['alias'])
                if eligible:
                    scoped_choices[key]=next(iter(eligible));added=True
                elif not requirement.get('optional',False):
                    raise PlanningError('Required provider unavailable for new workspace alias')
        if added:
            for consumer, alias, site, workspace in scoped_choices:
                choices.pop((consumer, alias), None)
            resolved = resolve_release(snapshot, document['python_metadata'], document['environment'], request['requested'],
                locked=locked, update=request.get('update', []), provider_choices=choices, scoped_provider_choices=scoped_choices,
                core_python=request.get('core_python', []), site_requirements=request.get('site_requirements'))
    if request['operation_type'] in ('suspend', 'enable', 'uninstall', 'unregister'):
        lock = state['release_lock']
    else:
        created_at = request.get('created_at')
        if not created_at:
            raise PlanningError('A fixed UTC creation time is required for reproducible release planning')
        lock = release_lock(resolved, document['provenance'], generation=state['release_lock']['generation'] + 1, created_at=created_at)
    installations = {scoped_installation_key(item): item for item in state['installations'] if item.get('state', 'installed') != 'not_installed'}
    for item in request['targets']:
        if item['action'] in ('uninstall', 'unregister', 'remove'):
            installations.pop(scoped_installation_key(item), None)
        else:
            installations[scoped_installation_key(item)] = item
    bindings = request.get('bindings')
    if bindings is None:
        bindings = scoped_bindings(resolved, list(installations.values()), state.get('bindings', []))
    bundle = prepare_plan(state, lock, resolved, request['targets'], bindings=bindings,
        endpoints=request.get('endpoints', state.get('endpoints', [])),
        permission_changes=request.get('permission_changes', []), trust_changes=request.get('trust_changes', []),
        operation_type=request['operation_type'], operation_id=request.get('operation_id'),
        created_at=request.get('created_at'), backup_policy=request.get('backup_policy', 'development_checkpoint'),
        catalog_snapshot_digest=data_digest(sorted(
            [{'plugin_id': item['manifest']['plugin']['id'], 'version': item['manifest']['plugin']['version'], 'digest': item['digest'], 'trust': item['trust']} for item in catalog],
            key=lambda item: (item['plugin_id'], item['version']))),
        resolution_reasons=resolved['reasons'])
    check_bundle(bundle, state)
    return bundle
