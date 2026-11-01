"""Pure sanitized deployment/profile projection shared by app and OS readers.

No Docker, filesystem, network, native ORM/plugin imports or authority grant.
The app receives only a metadata proposal; OS approval re-observes its source.
"""
import copy
import re

from .contracts import normalize_manifest, validate,checked_path,PACKAGE_VERSION
from .plans import data_digest, release_lock
from .resolution import PlanningError, resolve_release

PUBLISHED_RELEASE_PROTOCOL=1
PLATFORM_VERSION='0.1.12'


def catalog_validation_digest(catalog):
    return data_digest(sorted([{'plugin_id':item['manifest']['plugin']['id'],'version':item['manifest']['plugin']['version'],
        'digest':item['digest'],'trust':item['trust']} for item in catalog],key=lambda item:(item['plugin_id'],item['version'])))


def published_lock(derived,published):
    """Revalidate current executable contents, retaining publication evidence."""
    if not isinstance(published,dict) or set(published)!=set(derived):
        raise PlanningError('Exact independently published release lock required')
    expected=copy.deepcopy(derived)
    if not isinstance(published['plugins'],list) or len(published['plugins'])!=len(expected['plugins']):
        raise PlanningError('Published release plugin footprint changed')
    for actual,prior in zip(expected['plugins'],published['plugins']):
        trust=prior.get('trust') if isinstance(prior,dict) else None
        if (not isinstance(trust,dict) or set(trust)!={'model','signature_verified','policy_generation','warnings'}
                or trust['model'] not in ('operator-approved-exact-digest','unsigned-development')
                or trust['signature_verified'] is not False or type(trust['policy_generation']) is not int
                or trust['policy_generation']<1 or not isinstance(trust['warnings'],list)
                or any(not isinstance(warning,str) for warning in trust['warnings'])):
            raise PlanningError('Unsupported historical release trust evidence')
        actual['trust']=copy.deepcopy(trust)
    if expected!=published:
        raise PlanningError('Observed executable/environment/bindings differ from published release')
    return copy.deepcopy(published)


def runtime_inputs(runtime,catalog):
    """Derive trusted-image inputs without asserting any database installation."""
    artifacts = runtime['inventory'].get('artifacts', {})
    selected = []
    for plugin, artifact in sorted(artifacts.items()):
        matches = [item for item in catalog if item['manifest']['plugin']['id'] == plugin and item['digest'] == artifact['digest']]
        if len(matches) != 1:
            raise PlanningError('Running artifact is absent/untrusted in the independent catalog: ' + plugin)
        descriptor=matches[0];manifest=descriptor['manifest']
        package_path=checked_path('artifacts/'+artifact['file'])
        files=runtime['inventory']['files']
        if (artifact['plugin_id']!=plugin or artifact['version']!=manifest['plugin']['version']
                or files.get(package_path)!=descriptor['digest'][7:]):
            raise PlanningError('Image package bytes differ from the independent catalog identity')
        if manifest['runtime']['kind']=='native':
            addon=manifest['runtime']['addon_name'];prefix='backend/odoo_addons/'+addon+'/'
            expected={'addons/'+addon+'/'+name[len(prefix):]:digest for name,digest in descriptor['inventory'].items() if name.startswith(prefix)}
            actual={name:digest for name,digest in files.items() if name.startswith('addons/'+addon+'/')}
            if artifact['addon']!=addon or actual!=expected:
                raise PlanningError('Image native source differs from independently validated package bytes')
        selected.append(matches[0])
    provided = {item['manifest']['runtime'].get('addon_name') for item in selected}
    # Select the immutable image's version, not the host reader's version.
    # Old images retain the exact platform0.1.0 meaning in their published lock.
    platform_version=runtime.get('platform_version','0.1.0')
    if not isinstance(platform_version,str) or not PACKAGE_VERSION.fullmatch(platform_version):
        raise PlanningError('Invalid image platform version')
    if platform_version!='0.1.0' and runtime.get('native_manifests',{}).get('mp_core',{}).get('version')!='19.0.'+platform_version:
        raise PlanningError('Image platform/native core version mismatch')
    environment = {'platform_version': platform_version, 'native_runtime': 'odoo-19',
        'markers': runtime['markers'], 'accepted_wheel_tags': runtime['accepted_wheel_tags'],
        'core_addons': sorted(set(runtime['inventory']['native_addons']) - provided)}
    patches = runtime['inventory'].get('generated_patches', [])
    provenance = {'platform_version': platform_version, 'upstream_commit': runtime['inventory']['policy']['upstream_commit'],
        'native_patch_set_digest': data_digest(patches), 'core_inventory_digest': runtime['inventory_digest'],
        'python_lock_digest': runtime['python_lock_digest'],
        'python_runtime': {'version': runtime['python'], 'architecture': 'linux/' + runtime['architecture'], 'marker_environment': runtime['markers']}}
    return selected,environment,provenance


def project_deployment(configuration, observation, catalog):
    runtime = observation['runtime']
    selected,environment,provenance=runtime_inputs(runtime,catalog)
    choices = {}
    for site in observation['sites']:
        ids = {item['installation_id']: item['plugin_id'] for item in site['installations']}
        removed = {item['installation_id'] for item in site['installations'] if item['metadata_state'] == 'removed'}
        for item in site['bindings']:
            binding = validate('binding', item['descriptor'])
            if binding['consumer_installation_id'] in removed or binding['provider_installation_id'] in removed:
                raise PlanningError('Removed installation retains a live service binding')
            key = ids[binding['consumer_installation_id']], binding['alias'], binding['site_id'], binding['workspace_id']
            choices[key] = binding['provider_plugin_id']
    core_python = [item['name'] + '==' + item['version'] for item in runtime['python_metadata']]
    resolved = resolve_release(selected, runtime['python_metadata'], environment,
        {item['manifest']['plugin']['id']: '==' + item['manifest']['plugin']['version'] for item in selected},
        core_python=core_python, scoped_provider_choices=choices)
    lock = release_lock(resolved, provenance, generation=configuration['generation'], created_at=configuration['release_created_at'])
    if 'published_release' in configuration:
        lock=published_lock(lock,configuration['published_release'])
        for site in observation['sites']:
            if (site.get('release_digest')!=data_digest(lock) or site.get('release_generation')!=str(configuration['generation'])
                    or site.get('active_inventory_digest')!=runtime['inventory_digest']):
                raise PlanningError('Database publication differs from independently pinned release')
    by_plugin = {item['manifest']['plugin']['id']: item for item in selected}
    expanded, bindings, security = [], [], []
    for site in observation['sites']:
        installations = {item['installation_id']: item for item in site['installations']}
        for feature in site['features']:
            installation = installations[feature['installation_id']]
            if installation['runtime'] != 'native':
                raise PlanningError('External runtime state requires the G6 endpoint/health adapter')
            if feature.get('plugin_id', installation['plugin_id']) != installation['plugin_id']:
                raise PlanningError('Retained feature ownership differs from its installation')
            if installation['metadata_state'] == 'removed':
                # Saved declarations are inert history, not executable roots or
                # evidence of current catalog trust. They may name an earlier
                # version or a package no longer present in this image.
                manifest = normalize_manifest(installation['manifest'])
                if (manifest['plugin']['id'] != installation['plugin_id'] or manifest['plugin']['version'] != installation['version']
                        or manifest['runtime']['kind'] != 'native' or not re.fullmatch(r'sha256:[0-9a-f]{64}', installation['digest'])
                        or feature['feature_state'] != 'suspended'
                        or any(m['addon'] == manifest['runtime']['addon_name'] for m in site['native_modules'])
                        or any(g['installation_id'] == installation['installation_id'] and g['state'] == 'approved' for g in site['grants'])):
                    raise PlanningError('Removed installation has active native state, availability or grants')
                expanded.append(dict(installation_id=installation['installation_id'], site_id=site['site_id'],
                    workspace_id=feature['workspace_id'], plugin_id=installation['plugin_id'], state='not_installed',
                    feature_state='suspended', metadata_state='removed'))
                continue
            descriptor = by_plugin.get(installation['plugin_id'])
            if descriptor is None:
                raise PlanningError('Active installation requires its verified package in this image')
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
    if 'published_release' in configuration:state['catalog_validation_digest']=catalog_validation_digest(catalog)
    return {'state': state, 'environment': environment, 'provenance': provenance,
            'python_metadata': runtime['python_metadata']}


def public_profile(configuration, observation, catalog, observed_at):
    keys=['schema_version','deployment_id','image_id','generation','policy_version',
          'operator_authorization_generation','release_created_at']
    public={key:configuration[key] for key in keys}
    public['site_ids']=[item['site_id'] for item in configuration['sites']]
    if 'published_release' in configuration:public['published_release']=copy.deepcopy(configuration['published_release'])
    return {'schema_version':1,'configuration':public,'runtime':copy.deepcopy(observation['runtime']),
            'catalog':copy.deepcopy(catalog),'observed_at':observed_at}
