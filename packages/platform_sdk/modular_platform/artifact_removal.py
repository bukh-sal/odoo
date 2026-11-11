"""Data-only checks for a separately approved removal of packaged source.

Database uninstall and source removal are separate operations. These checks
consume independently observed image/site data; they do not grant authority,
import native code, delete archives, or assert that unknown sites were checked.
"""
import copy

from .contracts import checked_path
from .operator_os import OperatorError
from .plans import data_digest


def validate_removal_image(base, runtime, descriptor, plugins):
    """Allow only the exact package/addon subtraction from a distinct image."""
    removed = set(plugins)
    if not removed or len(removed) != len(plugins) or base is None:
        raise OperatorError('Artifact removal requires unique explicit packages and an observed base')
    if (descriptor['base_image_id'] == descriptor['target_image_id']
            or descriptor['inventory_digest'] != runtime['inventory_digest']
            or descriptor['runtime_digest'] != data_digest(runtime)):
        raise OperatorError('Artifact removal requires an exact distinct independently staged image')
    before, after = base['inventory'], runtime['inventory']
    old_artifacts = before.get('artifacts', {})
    if not removed <= old_artifacts.keys():
        raise OperatorError('Removal package is absent from the current executable inventory')
    expected_artifacts = {key: value for key, value in old_artifacts.items() if key not in removed}
    if after.get('artifacts', {}) != expected_artifacts:
        raise OperatorError('Removal image must preserve every surviving package identity')
    addons = {old_artifacts[key]['addon'] for key in removed}
    if len(addons) != len(removed) or None in addons or not addons <= before['native_addons'].keys():
        raise OperatorError('Removal requires unique inventoried native package addons')
    for key in ('python', 'architecture', 'markers', 'accepted_wheel_tags', 'python_metadata', 'python_lock_digest', 'published_release_protocol'):
        if base[key] != runtime[key]:
            raise OperatorError('Removal cannot change Python/runtime compatibility metadata')
    for image in (base, runtime):
        if any(image.get(key) for key in ('modified_files', 'missing_addon_files', 'unexpected_addon_files')):
            raise OperatorError('Removal requires exact verified source inventories')
    if after.get('generated_patches', []) != before.get('generated_patches', []):
        raise OperatorError('Removal cannot change upstream/generated patch provenance')
    expected_native = {key: value for key, value in before['native_addons'].items() if key not in addons}
    if after['native_addons'] != expected_native:
        raise OperatorError('Removal cannot change surviving native discovery metadata')
    if any(set(value['depends']) & addons for value in expected_native.values()):
        raise OperatorError('A surviving native addon still requires the removed package')
    expected_manifests = {key: value for key, value in base['native_manifests'].items() if key not in addons}
    if runtime['native_manifests'] != expected_manifests:
        raise OperatorError('Removal cannot change surviving native manifests')
    expected_policy = copy.deepcopy(before['policy'])
    if set(expected_policy.get('server_wide_modules', [])) & addons:
        raise OperatorError('Server-wide native modules cannot be removed by a package operation')
    for key in ('addons', 'explicit_install'):
        expected_policy[key] = [name for name in expected_policy[key] if name not in addons]
    # Source paths are build provenance, not executable authority. Each recipe
    # owns one package; preserve order within each source kind and allow only
    # the selected package count to disappear. Never transfer between kinds.
    old_sources = []
    removed_sources = 0
    for key in ('reference_packages', 'application_packages'):
        old_paths = expected_policy.get(key, [])
        new_paths = after['policy'].get(key, [])
        if not isinstance(old_paths, list) or not isinstance(new_paths, list):
            raise OperatorError('Removal package sources must be ordered lists')
        for path in old_paths + new_paths:
            checked_path(path)
        if (len(set(old_paths)) != len(old_paths) or len(set(new_paths)) != len(new_paths)
                or [name for name in old_paths if name in new_paths] != new_paths):
            raise OperatorError('Removal build policy may only subtract the selected package sources')
        old_sources.extend(old_paths)
        removed_sources += len(old_paths) - len(new_paths)
        if key in expected_policy:
            expected_policy[key] = list(new_paths)
    if len(set(old_sources)) != len(old_sources) or removed_sources != len(removed):
        raise OperatorError('Removal build policy may only subtract the selected package sources')
    if after['policy'] != expected_policy:
        raise OperatorError('Removal cannot change unrelated distribution policy')
    expected_inventory = copy.deepcopy(before)
    expected_inventory.update(artifacts=expected_artifacts, native_addons=expected_native, policy=expected_policy)
    if not expected_artifacts:
        expected_inventory.pop('artifacts', None)
    for key in ('reference_composition', 'package_composition'):
        composition = before.get(key)
        if composition is not None:
            if set(composition) != {'models', 'fields', 'ui_contributions'}:
                raise OperatorError('Unknown package composition requires explicit reconciliation')
            expected_composition = {name: {ident: owner for ident, owner in composition[name].items() if owner not in removed}
                                    for name in ('models', 'fields')}
            expected_composition['ui_contributions'] = [name for name in composition['ui_contributions']
                if not any(name.startswith(plugin + ':') for plugin in removed)]
            if after.get(key) != (expected_composition if expected_artifacts else None):
                label = 'reference composition' if key == 'reference_composition' else 'package composition'
                raise OperatorError('Removal ' + label + ' differs from exact package subtraction')
            if expected_artifacts:
                expected_inventory[key] = expected_composition
            else:
                expected_inventory.pop(key, None)
        elif after.get(key) is not None:
            raise OperatorError('Removal cannot add package composition metadata')
    prefixes = tuple('addons/' + addon + '/' for addon in addons)
    archives = {'artifacts/' + old_artifacts[key]['file'] for key in removed}
    for name in before['files'].keys() | after['files'].keys():
        checked_path(name)
    removed_files = {name for name in before['files'] if name.startswith(prefixes) or name in archives}
    if not archives <= removed_files or any(not any(name.startswith('addons/' + addon + '/') for name in removed_files) for addon in addons):
        raise OperatorError('Removal base is missing its exact package archive or addon source')
    expected_inventory['files'] = {name: value for name, value in before['files'].items() if name not in removed_files}
    actual_inventory = copy.deepcopy(after)
    # Empty optional maps are equivalent to the builder omitting them.
    if not actual_inventory.get('artifacts'):
        actual_inventory.pop('artifacts', None)
    if actual_inventory != expected_inventory:
        raise OperatorError('Removal image changed unrelated source or inventory metadata')
    return [dict(path=name, previous_sha256=before['files'][name], target_sha256=None) for name in sorted(removed_files)]


def validate_removal_sites(document, sites, plugins, base_runtime):
    """Reject active native state or supported authority at every observed site.

The independent observer must additionally prove that its configured sharing
site inventory is complete. An application's partial snapshot cannot do that.
"""
    removed = set(plugins)
    expected_sites = set(document['state']['site_ids'])
    if not removed or len(removed) != len(plugins) or len(sites) != len(expected_sites) or {s['site_id'] for s in sites} != expected_sites:
        raise OperatorError('Artifact removal requires every sharing site exactly once')
    artifacts = base_runtime['inventory'].get('artifacts', {})
    if not removed <= artifacts.keys():
        raise OperatorError('Removal package is absent from the observed base')
    addons = {artifacts[key]['addon'] for key in removed}
    for site in sites:
        required = {'site_id', 'installations', 'features', 'grants', 'bindings', 'native_modules', 'workspaces'}
        if not required <= site.keys():
            raise OperatorError('Incomplete sharing-site removal observation')
        installations = [row for row in site['installations'] if row['plugin_id'] in removed]
        ids = {row['installation_id'] for row in installations}
        if len(ids) != len(installations) or len({row['plugin_id'] for row in installations}) != len(installations):
            raise OperatorError('Ambiguous retained installation identity')
        historic_addons = {row['manifest']['runtime']['addon_name'] for row in installations if 'manifest' in row}
        if any(row['addon'] in addons | historic_addons for row in site['native_modules']):
            raise OperatorError('Artifact is still needed by an installed or pending native module')
        if any(row['metadata_state'] != 'removed' for row in installations):
            raise OperatorError('Artifact is still needed by site installation metadata')
        if any(row['feature_state'] != 'suspended' for row in site['features']
               if row['installation_id'] in ids or row.get('plugin_id') in removed):
            raise OperatorError('Removal cannot discard an enabled or degraded scope')
        if any(row['state'] == 'approved' for row in site['grants'] if row['installation_id'] in ids):
            raise OperatorError('Removal cannot discard an approved scoped grant')
        for row in site['bindings']:
            binding = row['descriptor']
            if (binding['consumer_installation_id'] in ids or binding['provider_installation_id'] in ids
                    or binding['provider_plugin_id'] in removed):
                raise OperatorError('Removal cannot discard a live service binding')
    return True


def validate_sharing_database_inventory(configuration, observation, inventory):
    """Completeness check for the qualified operator-owned DB-server profile.

    A single-host image cannot claim removal safety by silently omitting another
    database on that server. Unknown databases and nonempty maintenance schemas
    require explicit reconciliation; no database contents are read or deleted.
    """
    configured = configuration['sites']
    sites = {row['site_id'] for row in configured}
    databases = {row['database'] for row in configured}
    if (len(sites) != len(configured) or len(databases) != len(configured)
            or len(observation['sites']) != len(sites) or {row['site_id'] for row in observation['sites']} != sites):
        raise OperatorError('Sharing-site configuration/observation is incomplete or ambiguous')
    if (not isinstance(inventory, dict) or set(inventory) != {'databases', 'maintenance_relations'}
            or not isinstance(inventory['databases'], list) or len(set(inventory['databases'])) != len(inventory['databases'])
            or set(inventory['databases']) != databases | {'postgres'} or inventory['maintenance_relations'] != []):
        raise OperatorError('Unknown sharing database or nonempty maintenance schema blocks artifact removal')
    return dict(site_ids=sorted(sites), complete=True)


def removal_targets(document, sites, plugins):
    """List every retained scope, or explicit existing workspace contexts.

    A never-installed package has no database row to remove. Its canonical
    installation ID is a nomination identity only; execution creates no row.
    """
    from .lifecycle_planning import installation_id
    targets = []
    for site in sites:
        workspaces = {row['workspace_id'] for row in site['workspaces']}
        if not workspaces:
            raise OperatorError('Removal needs an existing workspace context for its frozen target envelope')
        for plugin in plugins:
            identity = installation_id(site, plugin)
            retained = {row['workspace_id'] for row in site['features'] if row['installation_id'] == identity}
            if not retained <= workspaces:
                raise OperatorError('Retained removal scopes differ from known workspaces')
            for workspace in sorted(retained or workspaces):
                targets.append(dict(installation_id=identity,site_id=site['site_id'],workspace_id=workspace,plugin_id=plugin,action='remove'))
    return sorted(targets,key=lambda row:(row['site_id'],row['workspace_id'],row['plugin_id'],row['installation_id']))


def prepare_staged_removal(document, sites, catalog, runtime, descriptor, *, targets, operation_id, created_at, base_runtime):
    """Reconstruct an exact source-only change; no database uninstall is mixed in."""
    from .contracts import plan_hash
    from .planning_cli import prepare_document
    from .plans import _display, check_bundle
    from .projection import runtime_inputs
    if not targets or any(row.get('action') != 'remove' for row in targets):
        raise OperatorError('Source removal requires explicit remove targets only')
    plugins = sorted({row['plugin_id'] for row in targets})
    validate_removal_sites(document,sites,plugins,base_runtime)
    expected_targets = removal_targets(document,sites,plugins)
    if sorted(targets,key=lambda row:(row['site_id'],row['workspace_id'],row['plugin_id'],row['installation_id'])) != expected_targets:
        raise OperatorError('Removal must list every sharing site and retained scope exactly')
    diff = validate_removal_image(base_runtime,runtime,descriptor,plugins)
    old={p['plugin_id']:p for p in document['state']['release_lock']['plugins']}
    external=[p for p in old.values() if p['runtime']=='external_service']
    selected, environment, provenance = runtime_inputs(runtime,catalog,external_plugins=external)
    staged = copy.deepcopy(document)
    staged.update(environment=environment,provenance=provenance,python_metadata=runtime['python_metadata'])
    staged['request'] = dict(operation_type='remove',requested={row['plugin_id']:'=='+row['version'] for row in selected},
        targets=expected_targets,core_python=[row['name']+'=='+row['version'] for row in runtime['python_metadata']],
        operation_id=operation_id,created_at=created_at)
    retained=[row['plugin_id'] for row in selected if row['plugin_id'] in old and row['digest']==old[row['plugin_id']]['digest']]
    bundle = prepare_document(staged,catalog,retained_trust_for=retained)
    actual = {row['plugin_id']:row['digest'] for row in bundle['operation_lock']['release']['plugins']}
    if (actual != {row['plugin_id']:row['digest'] for row in selected}
            or bundle['operation_lock']['bindings'] != document['state'].get('bindings', [])
            or bundle['operation_lock']['endpoints'] != document['state'].get('endpoints', [])
            or bundle['plan']['permission_changes'] or bundle['plan']['trust_changes']):
        raise OperatorError('Removal must preserve surviving executable identities/bindings/grants')
    lock = bundle['operation_lock']
    lock['platform_source_diff'] = diff
    lock['staged_image'] = copy.deepcopy(descriptor)
    lock['known_unknowns'].append('Only the selected package/addon is removed from the new runtime. Native database uninstall must already be complete; retained history, catalog archives, old images/checkpoints and old assets are preserved. Workers restart and old clients must refresh.')
    bundle['plan']['dependency_lock_digest'] = data_digest(lock)
    bundle['plan_hash'] = plan_hash(bundle['plan'])
    bundle['display'] = _display(bundle['plan'],lock)
    check_bundle(bundle,document['state'])
    return bundle
