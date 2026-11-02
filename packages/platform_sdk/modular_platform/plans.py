"""Exact data-only operation bundles under the frozen v1 approval envelope.

The plan hashes the full operation lock (including installation/workspace targets)
through dependency_lock_digest. An executor must load that exact lock, never just
accept the envelope or an application-supplied approval flag.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import hashlib
import re
from uuid import UUID, uuid4, uuid5

import rfc8785

from .contracts import canonical_plan, native_version, package_version, plan_hash, validate, validate_binding
from .resolution import PlanningError, binding_matches_scope


def data_digest(value):
    def check(item):
        if isinstance(item, float):
            raise PlanningError('Canonical operation metadata may not contain floats')
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise PlanningError('Canonical metadata requires string keys')
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)
    check(value)
    return 'sha256:' + hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def _uuid(value):
    try:
        valid = isinstance(value, str) and str(UUID(value)) == value
    except ValueError:
        valid = False
    if not valid:
        raise PlanningError('Canonical UUID target required')
    return value


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch('sha256:[0-9a-f]{64}', value):
        raise PlanningError('Immutable SHA256 identity required')
    return value


def scoped_installation_key(item):
    # One installation per site/plugin; many workspace feature scopes share it.
    return item['installation_id'], item['workspace_id']


def _check_installation_mapping(rows):
    identities, scopes, seen = {}, {}, set()
    for item in rows:
        identity = item['installation_id']
        owner = item['site_id'], item['plugin_id']
        if identity in identities and identities[identity] != owner or owner in scopes and scopes[owner] != identity:
            raise PlanningError('One stable plugin installation identity is required per site')
        key = scoped_installation_key(item)
        if key in seen:
            raise PlanningError('Duplicate workspace feature installation scope')
        seen.add(key)
        identities[identity], scopes[owner] = owner, identity


def applicable_migrations(manifest, previous_version):
    if previous_version is None:
        return []  # A fresh install initializes current state, not simulated upgrades.
    before, after = package_version(previous_version), package_version(manifest['plugin']['version'])
    if after <= before:
        raise PlanningError('Ordinary upgrade must strictly increase the package version')
    scripts = []
    for transition in manifest['upgrade']['transitions']:
        if before < package_version(transition['to']) <= after:
            scripts.extend({**item, 'target_version': transition['to']} for item in transition['scripts'])
    phases = {'pre': 0, 'post': 1, 'end': 2}
    # Odoo completes each phase across all applicable versions before advancing
    # to the next phase. This reviewed preimage must describe that native order.
    scripts.sort(key=lambda item: (phases[item['phase']], package_version(item['target_version']), item['path']))
    return scripts


def release_lock(solution, provenance, *, generation, created_at):
    required = {'platform_version', 'upstream_commit', 'native_patch_set_digest', 'python_runtime',
                'python_lock_digest', 'core_inventory_digest'}
    if not required <= provenance.keys() or type(generation) is not int or generation < 1:
        raise PlanningError('Complete release provenance and generation required')
    if not re.fullmatch('[0-9a-f]{40}', provenance['upstream_commit']):
        raise PlanningError('Exact upstream commit required')
    for key in ('native_patch_set_digest', 'python_lock_digest', 'core_inventory_digest'):
        _digest(provenance[key])
    if not {'version', 'architecture', 'marker_environment'} <= provenance['python_runtime'].keys():
        raise PlanningError('Exact Python runtime/architecture/marker environment required')
    environment = solution['target_environment']
    if (provenance['platform_version'] != environment['platform_version']
            or provenance['python_runtime']['version'] != environment['markers']['python_full_version']
            or provenance['python_runtime']['marker_environment'] != environment['markers']):
        raise PlanningError('Release provenance differs from the solved target environment')
    plugins = []
    frontend = {}
    for descriptor in solution['plugins']:
        manifest = descriptor['manifest']
        plugins.append({'plugin_id': manifest['plugin']['id'], 'version': manifest['plugin']['version'],
            'digest': _digest(descriptor['digest']), 'source': 'operator-catalog',
            'trust': copy.deepcopy(descriptor['trust']), 'runtime': manifest['runtime']['kind'],
            'native_addon': manifest['runtime'].get('addon_name'),
            'native_version': native_version(manifest['plugin']['version']) if manifest['runtime']['kind'] == 'native' else None,
            'manifest_digest': data_digest(manifest),
            'permissions': copy.deepcopy(manifest['permissions']),
            'activation': copy.deepcopy(manifest['activation']),
            'hard_dependencies': copy.deepcopy(manifest['dependencies']['plugins']),
            'data_ownership': copy.deepcopy(manifest['data']),
            'provided_apis': [{'service_id': item['id'], 'api_version': item['api_version']} for item in manifest['services']['provides']]})
        frontend[manifest['plugin']['id']] = {name: digest for name, digest in descriptor['inventory'].items()
            if name.startswith('frontend/') or '/static/' in name}
    return {'schema_version': 1, 'generator': 'modular-operator/0.1',
        'platform_version': provenance['platform_version'], 'upstream_commit': provenance['upstream_commit'],
        'native_patch_set_digest': provenance['native_patch_set_digest'],
        'python_runtime': copy.deepcopy(provenance['python_runtime']),
        'python_lock_digest': provenance['python_lock_digest'], 'core_inventory_digest': provenance['core_inventory_digest'],
        'python_solution_digest': data_digest(solution['python']), 'python_solution': copy.deepcopy(solution['python']),
        'plugins': plugins, 'native_order': list(solution['native_order']),
        'frontend_inventory': frontend, 'frontend_inventory_digest': data_digest(frontend),
        'service_selection': copy.deepcopy(solution['bindings']),
        'optional_integrations': copy.deepcopy(solution['optional_integrations']),
        'generation': generation, 'created_at': created_at}


def prepare_plan(state, target_release, solution, targets, *, bindings=(), endpoints=(),
                 permission_changes=(), trust_changes=(), operation_type='install',
                 operation_id=None, created_at=None, backup_policy='development_checkpoint',
                 catalog_snapshot_digest=None, resolution_reasons=None, feature_states=()):
    """Build a reviewable immutable bundle; no approval or execution is implied.

    `state` is the independently observed complete deployment snapshot. Targets
    explicitly enumerate installation/site/workspace/plugin/action; a workspace
    administrator's request must never be used as the observed snapshot.
    The executor will independently reconstruct/revalidate this same bundle.
    """
    state, target_release = copy.deepcopy(state), copy.deepcopy(target_release)
    operation_id = _uuid(operation_id or str(uuid4()))
    created_at = created_at or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    if not targets:
        raise PlanningError('At least one exact installation target is required')
    required = {'deployment_id', 'release_digest', 'release_lock', 'generation', 'installations',
                'site_ids', 'policy_version', 'operator_authorization_generation'}
    if not required <= state.keys():
        raise PlanningError('Complete independently observed base state required')
    _uuid(state['deployment_id'])
    if data_digest(state['release_lock']) != _digest(state['release_digest']):
        raise PlanningError('Observed release identity mismatch')
    old = {item['plugin_id']: item for item in state['release_lock']['plugins']}
    new = {item['manifest']['plugin']['id']: item for item in solution['plugins']}
    locked_new = {item['plugin_id']: item for item in target_release['plugins']}
    if set(new) != set(locked_new) or any(new[key]['digest'] != locked_new[key]['digest'] for key in new):
        raise PlanningError('Target release lock differs from solved artifacts')
    _check_installation_mapping(state['installations'])
    _check_installation_mapping(targets)
    _check_installation_mapping(list({scoped_installation_key(item): item for item in state['installations'] + list(targets)}.values()))
    installed = {scoped_installation_key(item): item for item in state['installations']}
    clean_targets, seen, artifacts, migrations = [], set(), {}, {}
    valid_actions = {'install', 'upgrade', 'suspend', 'enable', 'uninstall', 'unregister', 'remove','deploy'}
    for source in targets:
        if set(source) != {'installation_id', 'site_id', 'workspace_id', 'plugin_id', 'action'}:
            raise PlanningError('Exact target has unknown/missing fields')
        target = copy.deepcopy(source)
        for key in ('installation_id', 'site_id', 'workspace_id'):
            _uuid(target[key])
        if target['site_id'] not in state['site_ids'] or target['action'] not in valid_actions:
            raise PlanningError('Target site/action is outside this deployment')
        allowed_actions = {'install': {'install', 'upgrade'}, 'upgrade': {'install', 'upgrade'},
            'suspend': {'suspend'}, 'enable': {'enable'}, 'uninstall': {'uninstall', 'unregister'},
            'unregister': {'uninstall', 'unregister'}, 'remove': {'remove'},'deploy':{'deploy'},'core_upgrade':{'deploy'}}
        if target['action'] not in allowed_actions.get(operation_type, set()):
            raise PlanningError('Target action disagrees with the operation type')
        identity = scoped_installation_key(target)
        if identity in seen:
            raise PlanningError('Duplicate installation target')
        seen.add(identity)
        previous = installed.get(identity)
        if target['action'] == 'install':
            if previous and previous.get('state', 'installed') != 'not_installed' or any(item['site_id'] == target['site_id'] and item['workspace_id'] == target['workspace_id']
                               and item['plugin_id'] == target['plugin_id'] and item.get('state', 'installed') != 'not_installed' for item in installed.values()):
                raise PlanningError('Installation already exists at this exact scope')
        elif target['action'] == 'remove' and previous is None:
            if target['installation_id'] != str(uuid5(UUID(target['site_id']), 'plugin:' + target['plugin_id'])):
                raise PlanningError('Never-installed source removal requires its canonical nomination identity')
        elif not previous or any(previous[key] != target[key] for key in ('site_id', 'workspace_id', 'plugin_id')):
            raise PlanningError('Target installation identity or scope changed')
        if target['action'] == 'uninstall' and previous.get('state', 'installed') != 'installed':
            raise PlanningError('Native uninstall requires an installed site target')
        if target['action'] in ('enable', 'suspend', 'upgrade', 'deploy') and previous.get('state', 'installed') != 'installed':
            raise PlanningError('Lifecycle target is not installed; explicit installation or recovery is required')
        plugin = target['plugin_id']
        descriptor = new.get(plugin) if target['action'] in ('install', 'upgrade', 'enable', 'suspend','deploy') else None
        old_entry = old.get(plugin)
        if descriptor is None and old_entry is None:
            raise PlanningError('Target plugin is absent from the relevant release')
        if descriptor:
            manifest = descriptor['manifest']
            runtime, version, digest, addon = manifest['runtime']['kind'], manifest['plugin']['version'], descriptor['digest'], manifest['runtime'].get('addon_name')
            if target['action'] in ('suspend', 'enable') and ('workspace' not in manifest['activation']['scopes'] or not manifest['activation']['supports_feature_suspension']):
                raise PlanningError('Plugin does not support scoped feature suspension/enablement')
        else:
            runtime, version, digest, addon = (old_entry[key] for key in ('runtime', 'version', 'digest', 'native_addon'))
            manifest = None
        if target['action'] == 'upgrade':
            if not old_entry:
                raise PlanningError('Upgrade requires a previous release artifact')
            migrations[plugin] = applicable_migrations(manifest, old_entry['version']) if runtime == 'native' else []
        if target['action'] == 'uninstall' and runtime != 'native' or target['action'] == 'unregister' and runtime != 'external_service':
            raise PlanningError('Native uninstall and external unregister are distinct operations')
        key = plugin, target['action']
        artifacts[key] = {'plugin_id': plugin, 'version': version, 'digest': digest, 'runtime': runtime,
            'action': target['action'], 'native_addon': addon,
            'migration_digests': [item['digest'] for item in migrations.get(plugin, [])]}
        clean_targets.append(target)
    changed = {key for key, value in new.items() if key not in old or value['digest'] != old[key]['digest']}
    if operation_type in ('deploy','core_upgrade'):
        # Native maintenance targets all native scopes. Metadata-only roots are
        # retained exactly, including inert unregister tombstones; they do not
        # become fake native deploy targets or gain runtime-control authority.
        native_scopes={key:row for key,row in installed.items() if old.get(row['plugin_id'],{}).get('runtime')=='native'}
        external=[p for p in old.values() if p['runtime']=='external_service']
        if (changed or set(new)!=set(old) or seen!=set(native_scopes) or permission_changes or trust_changes
                or any(row.get('state')!='installed' or row.get('metadata_state','installed')!='installed' for row in native_scopes.values())
                or any(old.get(row['plugin_id'],{}).get('runtime') not in {'native','external_service'} for row in installed.values())
                or any(locked_new.get(p['plugin_id'])!=p for p in external)
                or any(item['runtime']!='native' for item in artifacts.values())):
            raise PlanningError('Platform deploy requires every installed native scope and unchanged artifacts/grants')
    covered = {target['plugin_id'] for target in clean_targets if target['action'] in ('install', 'upgrade')}
    if changed - covered:
        raise PlanningError('Every transitive artifact change needs explicit targets: ' + ', '.join(sorted(changed - covered)))
    for key in changed:
        for installation in state['installations']:
            if installation['plugin_id'] == key and scoped_installation_key(installation) not in seen:
                raise PlanningError('Changed native/shared artifact has an untargeted installation')
    removed = set(old) - set(new)
    if removed - {item['plugin_id'] for item in clean_targets if item['action'] == 'remove'}:
        raise PlanningError('Release artifact removal requires explicit removal targets')
    for target in clean_targets:
        if target['action'] == 'remove' and any(item['plugin_id'] == target['plugin_id'] and item.get('state', 'installed') != 'not_installed' for item in state['installations']):
            raise PlanningError('Artifact is still needed by a site installation')
        if target['action'] == 'uninstall':
            if any(item['plugin_id'] == target['plugin_id'] and item['site_id'] == target['site_id'] and scoped_installation_key(item) not in seen for item in state['installations']):
                raise PlanningError('Native uninstall must target every workspace installation in its site database')
        if target['action'] in ('suspend', 'uninstall', 'unregister'):
            for dependent in state['installations']:
                if dependent.get('state', 'installed') == 'not_installed':
                    continue
                if scoped_installation_key(dependent) in seen or dependent['site_id'] != target['site_id'] or dependent['workspace_id'] != target['workspace_id']:
                    continue
                if target['action'] == 'suspend' and dependent.get('feature_state') == 'suspended':
                    continue
                entry = old.get(dependent['plugin_id'], {})
                providers = {item['provider'] for item in state['release_lock'].get('service_selection', [])
                             if item['consumer'] == dependent['plugin_id'] and not item['optional'] and binding_matches_scope(item, dependent['site_id'], dependent['workspace_id'])}
                if target['plugin_id'] in set(entry.get('hard_dependencies', {})) | providers:
                    raise PlanningError('Explicit dependent cascade target required: ' + dependent['plugin_id'])
        if target['action'] == 'enable':
            required_plugins = set(new[target['plugin_id']]['manifest']['dependencies']['plugins'])
            required_plugins.update(item['provider'] for item in solution['bindings']
                if item['consumer'] == target['plugin_id'] and not item['optional']
                and binding_matches_scope(item, target['site_id'], target['workspace_id']))
            for plugin in required_plugins:
                provider_installation = next((item for item in state['installations'] if item['site_id'] == target['site_id']
                    and item['workspace_id'] == target['workspace_id'] and item['plugin_id'] == plugin), None)
                enabling = provider_installation and any(item['action'] == 'enable' and scoped_installation_key(item) == scoped_installation_key(provider_installation) for item in clean_targets)
                if (not provider_installation or provider_installation['state'] != 'installed'
                        or provider_installation.get('metadata_state', 'installed') != 'installed'
                        or provider_installation.get('feature_state', 'enabled') != 'enabled' and not enabling):
                    raise PlanningError('Required provider must be installed and enabled at this scope: ' + plugin)
                if new[plugin]['manifest']['runtime']['kind'] == 'external_service':
                    key = provider_installation['installation_id'] + ':' + target['workspace_id']
                    health = state.get('service_health', {}).get(key, {})
                    expected_image = new[plugin]['manifest']['external_service']['expected_image'].split('@', 1)[1]
                    if health.get('state') != 'healthy' or health.get('expected_image_digest') != expected_image:
                        raise PlanningError('Required external provider needs independently verified current health/image identity')
    if operation_type in ('suspend', 'enable', 'unregister') and data_digest(target_release) != state['release_digest']:
        raise PlanningError('Feature/database-only operation must preserve the executable release')
    if operation_type == 'uninstall':
        expected_release = copy.deepcopy(state['release_lock'])
        expected_release.update(generation=expected_release['generation'] + 1, created_at=created_at,
                                service_selection=copy.deepcopy(solution['bindings']))
        scopes = {(row['plugin_id'], row['workspace_id']) for row in clean_targets}
        revocations = {(row.get('plugin_id'), row.get('workspace_id'), row.get('capability')) for row in permission_changes}
        if (target_release != expected_release or trust_changes or len(revocations) != len(permission_changes)
                or any(set(row) != {'plugin_id', 'workspace_id', 'capability', 'action'} or row['action'] != 'revoke'
                       or (row['plugin_id'], row['workspace_id']) not in scopes for row in permission_changes)):
            raise PlanningError('Native uninstall requires a new epoch, unchanged executable identities and surviving service selections')
    ordered_targets = sorted(clean_targets, key=lambda item: (item['site_id'], item['workspace_id'], item['plugin_id'], item['installation_id']))
    feature_states = copy.deepcopy(list(feature_states))
    if feature_states:
        expected_scopes = {(r['installation_id'], r['site_id'], r['workspace_id']) for r in clean_targets}
        if (operation_type != 'install' or any(t['action'] != 'install' for t in clean_targets)
                or len(feature_states) != len(expected_scopes)
                or any(not isinstance(r, dict) or set(r) != {'installation_id', 'site_id', 'workspace_id', 'availability'}
                       or r['availability'] not in ('enabled', 'suspended') for r in feature_states)
                or {(r['installation_id'], r['site_id'], r['workspace_id']) for r in feature_states} != expected_scopes):
            raise PlanningError('Exact post-install feature states must cover every native install target')
        states = {(r['installation_id'], r['workspace_id']): r['availability'] for r in feature_states}
        for change in permission_changes:
            target = next((t for t in clean_targets if t['plugin_id'] == change['plugin_id'] and t['workspace_id'] == change['workspace_id']), None)
            if target is None or change['action'] != 'grant' or states[(target['installation_id'], target['workspace_id'])] != 'enabled':
                raise PlanningError('Suspended restored scopes cannot receive renewed grants')
    bindings, endpoints = copy.deepcopy(list(bindings)), copy.deepcopy(list(endpoints))
    target_installations = {key: value for key, value in installed.items() if value.get('state', 'installed') != 'not_installed'}
    for target in clean_targets:
        if target['action'] in ('uninstall', 'unregister', 'remove'):
            target_installations.pop(scoped_installation_key(target), None)
        else:
            target_installations[scoped_installation_key(target)] = target
    bound_aliases = set()
    for binding in bindings:
        validate('binding', binding)
        consumer = target_installations.get((binding['consumer_installation_id'], binding['workspace_id']))
        provider_install = target_installations.get((binding['provider_installation_id'], binding['workspace_id']))
        if not consumer or not provider_install or any(item[key] != binding[key] for item in (consumer, provider_install) for key in ('site_id', 'workspace_id')):
            raise PlanningError('Binding scope/installation is outside the exact operation')
        if provider_install['plugin_id'] != binding['provider_plugin_id'] or consumer['plugin_id'] not in new or provider_install['plugin_id'] not in new:
            raise PlanningError('Binding plugin ownership mismatch')
        requirements = new[consumer['plugin_id']]['manifest']['services']['requires']
        requirement = next((item for item in requirements if item['alias'] == binding['alias']), None)
        providers = new[provider_install['plugin_id']]['manifest']['services']['provides']
        provider = next((item for item in providers if item['id'] == binding['service_id'] and item['api_version'] == binding['api_version']), None)
        if not requirement or not provider:
            raise PlanningError('Binding references an undeclared alias or service API')
        validate_binding(binding, requirement, {**provider, 'plugin_id': provider_install['plugin_id'], 'installation_id': provider_install['installation_id']})
        selected = next((item for item in solution['bindings'] if item['consumer'] == consumer['plugin_id'] and item['alias'] == binding['alias'] and item['provider'] == provider_install['plugin_id'] and binding_matches_scope(item, binding['site_id'], binding['workspace_id'])), None)
        if not selected or selected['provider'] != provider_install['plugin_id'] or selected['api_version'] != binding['api_version']:
            raise PlanningError('Scoped binding disagrees with the solved provider selection')
        identity = binding['consumer_installation_id'], binding['workspace_id'], binding['alias']
        if identity in bound_aliases:
            raise PlanningError('Duplicate consumer-local binding alias')
        bound_aliases.add(identity)
    for installation in target_installations.values():
        if installation['plugin_id'] not in new:
            continue
        for requirement in new[installation['plugin_id']]['manifest']['services']['requires']:
            if not requirement.get('optional', False) and (installation['installation_id'], installation['workspace_id'], requirement['alias']) not in bound_aliases:
                raise PlanningError('Missing required scoped binding')
    for endpoint in endpoints:
        validate('endpoint', endpoint)
        installation = target_installations.get((endpoint['installation_id'], endpoint['workspace_id']))
        if not installation or any(installation[key] != endpoint[key] for key in ('site_id', 'workspace_id')) or installation['plugin_id'] not in new:
            raise PlanningError('Endpoint installation scope mismatch')
        manifest = new[installation['plugin_id']]['manifest']
        if manifest['runtime']['kind'] != 'external_service' or endpoint['endpoint_config'] != manifest['external_service']['endpoint_config'] or endpoint['expected_image_digest'] != manifest['external_service']['expected_image'].split('@', 1)[1]:
            raise PlanningError('Endpoint expectation differs from external metadata')
    for installation in target_installations.values():
        if installation['plugin_id'] in new and new[installation['plugin_id']]['manifest']['runtime']['kind'] == 'external_service' and not any(item['installation_id'] == installation['installation_id'] and item['workspace_id'] == installation['workspace_id'] for item in endpoints):
            raise PlanningError('External installation requires its independently configured endpoint')
    if len({item['binding_id'] for item in bindings}) != len(bindings) or len({item['endpoint_config'] for item in endpoints}) != len(endpoints):
        raise PlanningError('Duplicate binding or endpoint identity')
    operation_lock = {'schema_version': 1, 'operation_id': operation_id, 'targets': ordered_targets,
        'catalog_snapshot_digest': _digest(catalog_snapshot_digest) if catalog_snapshot_digest else data_digest(target_release['plugins']),
        'resolution_reasons': copy.deepcopy(resolution_reasons or {}),
        'release': target_release, 'bindings': sorted(bindings, key=lambda item: item['binding_id']),
        'endpoints': sorted(endpoints, key=lambda item: item['endpoint_config']),
        'migration_order': migrations,
        'declaration_changes': {key: {'previous_permissions': old.get(key, {}).get('permissions'),
            'target_permissions': new[key]['manifest']['permissions'],
            'previous_activation': old.get(key, {}).get('activation'),
            'target_activation': new[key]['manifest']['activation']} for key in sorted(changed)},
        'known_unknowns': ['Native Python and same-origin frontend code is fully trusted.',
                           'Author destructive=false does not prove migration safety.']}
    if feature_states:
        operation_lock['feature_states'] = sorted(feature_states, key=lambda r: (r['site_id'], r['workspace_id'], r['installation_id']))
        operation_lock['known_unknowns'].append('Native schema is restored site-wide. Review the exact post-install feature states: suspended scopes receive no renewed grants and remain unavailable.')
    if 'catalog_validation_digest' in state:
        if state['catalog_validation_digest']!=operation_lock['catalog_snapshot_digest']:
            raise PlanningError('Catalog snapshot differs from independently observed current validation')
        operation_lock['current_catalog_validation_digest']=state['catalog_validation_digest']
    destructive = operation_type=='core_upgrade' or any(item['action'] == 'uninstall' for item in ordered_targets) or any(
        new[key]['manifest']['upgrade']['destructive'] for key in changed)
    plan = {'schema_version': 1, 'operation_id': operation_id, 'operation_type': operation_type,
        'created_at': created_at, 'deployment_id': state['deployment_id'],
        'site_ids': sorted({item['site_id'] for item in ordered_targets}),
        'base_state_digest': data_digest(state), 'base_release_digest': state['release_digest'],
        'target_release_digest': data_digest(target_release),
        'artifacts': [artifacts[key] for key in sorted(artifacts)],
        'dependency_lock_digest': data_digest(operation_lock),
        'bindings': [{'binding_id': item['binding_id'], 'generation': item['generation'], 'digest': data_digest(item)} for item in operation_lock['bindings']],
        'endpoints': [{'endpoint_config': item['endpoint_config'], 'generation': item['generation'], 'digest': data_digest(item), 'expected_image_digest': item['expected_image_digest']} for item in operation_lock['endpoints']],
        'permission_changes': sorted(copy.deepcopy(list(permission_changes)), key=lambda item: (item['plugin_id'], item['workspace_id'], item['capability'], item['action'])),
        'trust_changes': sorted(copy.deepcopy(list(trust_changes)), key=lambda item: (item['artifact_digest'], item['decision'])),
        'destructive': destructive,
        'backup': {'required': any(item['runtime']=='external_service' or item['runtime'] == 'native'
                    and item['action'] in ('install', 'upgrade', 'uninstall','remove','deploy') for item in artifacts.values()),
                   'policy_id': backup_policy, 'retain_previous_release': True},
        'policy_version': state['policy_version'], 'operator_authorization_generation': state['operator_authorization_generation']}
    canonical_plan(plan)
    display = _display(plan, operation_lock)
    return {'plan': plan, 'plan_hash': plan_hash(plan), 'operation_lock': operation_lock, 'display': display}


def _display(plan, operation_lock):
    display={'targets': operation_lock['targets'], 'artifacts': plan['artifacts'],
                'required_local_step': 'Independent local operator approval of the exact plan hash, then CLI apply.',
                'native_code_requires_trust': any(item['runtime'] == 'native' for item in plan['artifacts']),
                'restart_required': (plan['operation_type'] in ('enable','suspend') and plan['backup']['required']) or any(item['runtime'] == 'external_service' or (item['runtime'] == 'native' and item['action'] in ('install', 'upgrade', 'uninstall', 'remove','deploy')) for item in plan['artifacts']),
                'feature_suspension_unloads_code': False,
                'permission_changes': plan['permission_changes'], 'trust_changes': plan['trust_changes'],
                'declaration_changes': operation_lock['declaration_changes'],
                'resolution_reasons': operation_lock['resolution_reasons'],
                'artifact_trust': [{'plugin_id': item['plugin_id'], 'digest': item['digest'], 'trust': item['trust']} for item in operation_lock['release']['plugins']],
                'backup': plan['backup'], 'destructive': plan['destructive'],
                'known_unknowns': operation_lock['known_unknowns']}
    if 'staged_image' in operation_lock:
        display['staged_image']=copy.deepcopy(operation_lock['staged_image'])
    if 'current_catalog_validation_digest' in operation_lock:
        display['current_catalog_validation_digest']=operation_lock['current_catalog_validation_digest']
    if 'platform_source_diff' in operation_lock:
        display['platform_source_diff']=copy.deepcopy(operation_lock['platform_source_diff'])
    if 'native_core_changes' in operation_lock:
        display['native_core_changes']=copy.deepcopy(operation_lock['native_core_changes'])
    if 'native_uninstall_impact' in operation_lock:
        display['native_uninstall_impact_digest'] = data_digest(operation_lock['native_uninstall_impact'])
    if 'feature_states' in operation_lock:
        display['feature_states'] = copy.deepcopy(operation_lock['feature_states'])
    return display


def check_bundle(bundle, current_state):
    """Fail closed on stale state, lock tampering or envelope/display mismatch."""
    if not isinstance(bundle, dict) or set(bundle) != {'plan', 'plan_hash', 'operation_lock', 'display'}:
        raise PlanningError('Unknown or missing immutable operation bundle fields')
    plan, lock = bundle['plan'], bundle['operation_lock']
    canonical_plan(plan)
    if plan_hash(plan) != bundle['plan_hash'] or data_digest(lock) != plan['dependency_lock_digest']:
        raise PlanningError('Plan or operation lock digest mismatch')
    if data_digest(current_state) != plan['base_state_digest'] or current_state['release_digest'] != plan['base_release_digest']:
        raise PlanningError('Stale plan: deployment state or generation changed')
    if data_digest(lock['release']) != plan['target_release_digest'] or lock['operation_id'] != plan['operation_id']:
        raise PlanningError('Target release or operation identity mismatch')
    expected_bindings = [{'binding_id': item['binding_id'], 'generation': item['generation'], 'digest': data_digest(item)} for item in lock['bindings']]
    expected_endpoints = [{'endpoint_config': item['endpoint_config'], 'generation': item['generation'], 'digest': data_digest(item), 'expected_image_digest': item['expected_image_digest']} for item in lock['endpoints']]
    if expected_bindings != plan['bindings'] or expected_endpoints != plan['endpoints']:
        raise PlanningError('Bound provider or endpoint metadata mismatch')
    if bundle['display'] != _display(plan, lock):
        raise PlanningError('Displayed operation differs from approved data')
    return True
