"""Pure sanitized deployment/profile projection shared by app and OS readers.

No Docker, filesystem, network, native ORM/plugin imports or authority grant.
The app receives only a metadata proposal; OS approval re-observes its source.
"""
import copy

from .contracts import normalize_manifest, validate
from .plans import data_digest, release_lock
from .resolution import PlanningError, resolve_release


def project_deployment(configuration, observation, catalog):
    runtime = observation['runtime']
    artifacts = runtime['inventory'].get('artifacts', {})
    selected = []
    for plugin, artifact in sorted(artifacts.items()):
        matches = [item for item in catalog if item['manifest']['plugin']['id'] == plugin and item['digest'] == artifact['digest']]
        if len(matches) != 1:
            raise PlanningError('Running artifact is absent/untrusted in the independent catalog: ' + plugin)
        selected.append(matches[0])
    provided = {item['manifest']['runtime'].get('addon_name') for item in selected}
    environment = {'platform_version': '0.1.0', 'native_runtime': 'odoo-19',
        'markers': runtime['markers'], 'accepted_wheel_tags': runtime['accepted_wheel_tags'],
        'core_addons': sorted(set(runtime['inventory']['native_addons']) - provided)}
    choices = {}
    for site in observation['sites']:
        ids = {item['installation_id']: item['plugin_id'] for item in site['installations']}
        for item in site['bindings']:
            binding = validate('binding', item['descriptor'])
            key = ids[binding['consumer_installation_id']], binding['alias'], binding['site_id'], binding['workspace_id']
            choices[key] = binding['provider_plugin_id']
    core_python = [item['name'] + '==' + item['version'] for item in runtime['python_metadata']]
    resolved = resolve_release(selected, runtime['python_metadata'], environment,
        {item['manifest']['plugin']['id']: '==' + item['manifest']['plugin']['version'] for item in selected},
        core_python=core_python, scoped_provider_choices=choices)
    patches = runtime['inventory'].get('generated_patches', [])
    provenance = {'platform_version': '0.1.0', 'upstream_commit': runtime['inventory']['policy']['upstream_commit'],
        'native_patch_set_digest': data_digest(patches), 'core_inventory_digest': runtime['inventory_digest'],
        'python_lock_digest': runtime['python_lock_digest'],
        'python_runtime': {'version': runtime['python'], 'architecture': 'linux/' + runtime['architecture'], 'marker_environment': runtime['markers']}}
    lock = release_lock(resolved, provenance, generation=configuration['generation'], created_at=configuration['release_created_at'])
    by_plugin = {item['manifest']['plugin']['id']: item for item in selected}
    expanded, bindings, security = [], [], []
    for site in observation['sites']:
        installations = {item['installation_id']: item for item in site['installations']}
        for feature in site['features']:
            installation = installations[feature['installation_id']]
            if installation['runtime'] != 'native':
                raise PlanningError('External runtime state requires the G6 endpoint/health adapter')
            descriptor = by_plugin[installation['plugin_id']]
            if installation['digest'] != descriptor['digest'] or normalize_manifest(installation['manifest']) != descriptor['manifest']:
                raise PlanningError('Database installation metadata differs from verified artifact')
            native_state = {item['addon']: item['state'] for item in site['native_modules']}.get(descriptor['manifest']['runtime'].get('addon_name'))
            expanded.append({'installation_id': installation['installation_id'], 'site_id': site['site_id'],
                'workspace_id': feature['workspace_id'], 'plugin_id': installation['plugin_id'],
                'state': 'installed' if native_state == 'installed' else 'not_installed',
                'feature_state': feature['feature_state'], 'metadata_state': installation['metadata_state']})
        bindings.extend(item['descriptor'] for item in site['bindings'])
        security.append({'site_id': site['site_id'], 'workspaces': site['workspaces'], 'memberships': site['memberships'],
                         'grants': site['grants'], 'bindings': site['bindings'], 'native_modules': site['native_modules']})
    state = {'deployment_id': configuration['deployment_id'], 'site_ids': sorted(item['site_id'] for item in observation['sites']),
        'generation': configuration['generation'], 'release_lock': lock, 'release_digest': data_digest(lock),
        'installations': sorted(expanded, key=lambda item: (item['installation_id'], item['workspace_id'])),
        'bindings': sorted(bindings, key=lambda item: item['binding_id']), 'endpoints': [],
        'security_metadata_digest': data_digest(security), 'image_id': observation['image_id'],
        'policy_version': configuration['policy_version'], 'operator_authorization_generation': configuration['operator_authorization_generation']}
    return {'state': state, 'environment': environment, 'provenance': provenance,
            'python_metadata': runtime['python_metadata']}


def public_profile(configuration, observation, catalog, observed_at):
    keys=['schema_version','deployment_id','image_id','generation','policy_version',
          'operator_authorization_generation','release_created_at']
    public={key:configuration[key] for key in keys}
    public['site_ids']=[item['site_id'] for item in configuration['sites']]
    return {'schema_version':1,'configuration':public,'runtime':copy.deepcopy(observation['runtime']),
            'catalog':copy.deepcopy(catalog),'observed_at':observed_at}
