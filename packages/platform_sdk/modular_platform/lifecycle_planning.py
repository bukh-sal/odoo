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


def validate_install_targets(document, sites, targets, feature_states=(), *, entries=None, service_selection=None):
    by_site = {site['site_id']: site for site in sites}
    release = entries if entries is not None else {item['plugin_id']: item for item in document['state']['release_lock']['plugins']}
    selections = service_selection if service_selection is not None else document['state']['release_lock']['service_selection']
    states = {(r['installation_id'], r['workspace_id']): r['availability'] for r in feature_states}
    for target in targets:
        site = by_site.get(target['site_id'])
        activating = states.get((target['installation_id'], target['workspace_id']), 'enabled') == 'enabled'
        if site is None or not any(item['workspace_id'] == target['workspace_id'] and (item['state'] == 'active' or not activating)
                                   for item in site['workspaces']):
            raise PlanningError('Install target requires an independently observed active workspace')
        if target['action'] != 'install' or target['plugin_id'] not in release or release[target['plugin_id']]['runtime'] != 'native':
            raise PlanningError('Current-image installation accepts native install targets only')
        if target['installation_id'] != installation_id(site, target['plugin_id']):
            raise PlanningError('Install target differs from the independently derived site installation identity')
        previous = next((item for item in site['installations'] if item['plugin_id'] == target['plugin_id']), None)
        if previous and previous['metadata_state'] != 'installed':
            addon = release[target['plugin_id']]['native_addon']
            native = next((r for r in site.get('native_modules', []) if r['addon'] == addon), None)
            scopes = [f for f in site.get('features', []) if f['installation_id'] == previous['installation_id']]
            if (previous['metadata_state'] != 'removed' or native is not None
                    or any(f['feature_state'] != 'suspended' for f in scopes)):
                raise PlanningError('Existing site installation requires explicit reconciliation before new activation')
        required = set(release[target['plugin_id']]['hard_dependencies'])
        required.update(item['provider'] for item in selections
            if item['consumer'] == target['plugin_id'] and not item['optional']
            and binding_matches_scope(item, target['site_id'], target['workspace_id']))
        for plugin in required:
            targeted = any(item['plugin_id'] == plugin and item['site_id'] == target['site_id']
                and item['workspace_id'] == target['workspace_id'] and item['action'] == 'install' for item in targets)
            existing = next((item for item in document['state']['installations'] if item['plugin_id'] == plugin
                and item['site_id'] == target['site_id'] and item['workspace_id'] == target['workspace_id']), None)
            if not targeted and (not existing or existing['state'] != 'installed'
                    or existing['metadata_state'] != 'installed' or activating and existing['feature_state'] != 'enabled'):
                raise PlanningError('Install target omits a required scoped provider/dependency')


def install_scope_spec(document, sites, *, activation_targets, entries=None, service_selection=None):
    """Expand explicit activation requests into all site-wide retained effects.

    Tombstone scopes and necessary inactive dependencies are included as exact
    install targets, but only activation requests/dependencies receive feature
    availability or grants. The complete map is part of the hashed lock.
    """
    if not activation_targets:
        raise PlanningError('At least one explicit feature activation target is required')
    entries = entries if entries is not None else {r['plugin_id']: r for r in document['state']['release_lock']['plugins']}
    selections = service_selection if service_selection is not None else document['state']['release_lock']['service_selection']
    by_site = {s['site_id']: s for s in sites}
    existing = {(r['site_id'], r['workspace_id'], r['plugin_id']): r for r in document['state']['installations']}
    targets, enabled, restoring = {}, set(), False

    def add(site_id, workspace, plugin, activate):
        site = by_site.get(site_id)
        if site is None or plugin not in entries or entries[plugin]['runtime'] != 'native':
            raise PlanningError('Native installation dependency is outside the observed image/site')
        key = site_id, workspace, plugin
        targets[key] = dict(installation_id=installation_id(site, plugin), site_id=site_id,
                            workspace_id=workspace, plugin_id=plugin, action='install')
        if activate: enabled.add(key)

    for target in activation_targets:
        if (not isinstance(target, dict) or set(target) != {'installation_id', 'site_id', 'workspace_id', 'plugin_id', 'action'}
                or target['action'] != 'install'):
            raise PlanningError('Exact native installation activation targets required')
        site = by_site.get(target['site_id'])
        if site is None or target['installation_id'] != installation_id(site, target['plugin_id']):
            raise PlanningError('Install target differs from the independently derived site installation identity')
        previous = existing.get((target['site_id'], target['workspace_id'], target['plugin_id']))
        if previous and previous['state'] == 'installed':
            raise PlanningError('Requested plugin already installed at this workspace')
        add(target['site_id'], target['workspace_id'], target['plugin_id'], True)
    while True:
        before = len(targets), len(enabled)
        for key, target in list(targets.items()):
            site_id, workspace, plugin = key
            site = by_site[site_id]
            previous = next((r for r in site['installations'] if r['plugin_id'] == plugin), None)
            if previous and previous['metadata_state'] == 'removed':
                restoring = True
                for scope in site.get('features', []):
                    if scope['installation_id'] == previous['installation_id']:
                        add(site_id, scope['workspace_id'], plugin, False)
            required = set(entries[plugin]['hard_dependencies'])
            required.update(r['provider'] for r in selections
                            if r['consumer'] == plugin and not r['optional'] and binding_matches_scope(r, site_id, workspace))
            for provider in sorted(required):
                provider_key = site_id, workspace, provider
                current = existing.get(provider_key)
                if current and current['state'] == 'installed':
                    if (current.get('metadata_state', 'installed') != 'installed'
                            or key in enabled and current.get('feature_state', 'enabled') != 'enabled'):
                        raise PlanningError('Required provider must be explicitly enabled before installation')
                    continue
                add(site_id, workspace, provider, key in enabled)
        if before == (len(targets), len(enabled)): break
    order = lambda r: (r['site_id'], r['workspace_id'], r['plugin_id'], r['installation_id'])
    ordered = sorted(targets.values(), key=order)
    feature_states = [dict(installation_id=r['installation_id'], site_id=r['site_id'], workspace_id=r['workspace_id'],
                          availability='enabled' if (r['site_id'], r['workspace_id'], r['plugin_id']) in enabled else 'suspended') for r in ordered]
    validate_install_targets(document, sites, ordered, feature_states, entries=entries, service_selection=selections)
    grants = {(s['site_id'], g['workspace_id'], g['installation_id'], g['capability']): g
              for s in sites for g in s.get('grants', [])}
    changes = []
    for row in ordered:
        if (row['site_id'], row['workspace_id'], row['plugin_id']) not in enabled: continue
        for request in entries[row['plugin_id']]['permissions']['requests']:
            grant = grants.get((row['site_id'], row['workspace_id'], row['installation_id'], request['capability']))
            if grant is None or grant['state'] != 'approved':
                changes.append(dict(plugin_id=row['plugin_id'], workspace_id=row['workspace_id'], capability=request['capability'], action='grant'))
    return dict(targets=ordered, permission_changes=changes,
                feature_states=feature_states if restoring or any(r['availability']=='suspended' for r in feature_states) else [])


def prepare_current_install_targets(document, sites, catalog, *, activation_targets, operation_id, created_at):
    spec=install_scope_spec(document,sites,activation_targets=activation_targets)
    request=dict(operation_type='install',requested={},targets=spec['targets'],permission_changes=spec['permission_changes'],
                 operation_id=operation_id,created_at=created_at)
    if spec['feature_states']:request['feature_states']=spec['feature_states']
    retained=[p['plugin_id'] for p in document['state']['release_lock']['plugins']]
    return prepare_document({**document, 'request': request}, catalog,retained_trust_for=retained)


def install_activation_targets(bundle):
    """Validate optional data-only post-states before independent reconstruction."""
    lock = bundle['operation_lock']; targets = lock['targets']
    if 'feature_states' not in lock: return targets
    rows = lock['feature_states']
    keys = lambda r: (r['installation_id'], r['site_id'], r['workspace_id'])
    if (not isinstance(rows, list) or len(rows) != len(targets)
            or any(not isinstance(r, dict) or set(r) != {'installation_id', 'site_id', 'workspace_id', 'availability'}
                   or r['availability'] not in ('enabled', 'suspended') for r in rows)
            or {keys(r) for r in rows} != {keys(t) for t in targets}):
        raise PlanningError('Exact native post-install feature-state map required')
    enabled = {keys(r) for r in rows if r['availability'] == 'enabled'}
    return [t for t in targets if keys(t) in enabled]


def prepare_current_feature(document, sites, catalog, *, targets, operation_type, operation_id, created_at):
    """Explicit enable may request renewed declared grants; OS approval binds it.

    Suspension never revokes or renews grants. Enablement after reinstall must
    not silently reuse a revoked approval or create missing native bindings.
    """
    if operation_type not in ('suspend', 'enable'):
        raise PlanningError('Feature planning requires suspension or enablement')
    entries = {r['plugin_id']: r for r in document['state']['release_lock']['plugins']}
    by_site = {s['site_id']: s for s in sites}
    changes = []
    for target in targets:
        site = by_site.get(target['site_id'])
        if site is None or not any(w['workspace_id'] == target['workspace_id'] and w['state'] == 'active' for w in site['workspaces']):
            raise PlanningError('Feature activation requires an independently observed active workspace')
        if target['action'] != operation_type:
            raise PlanningError('Feature target action differs from operation')
        if operation_type == 'enable':
            for request in entries[target['plugin_id']]['permissions']['requests']:
                grant = next((g for g in site.get('grants', []) if g['installation_id'] == target['installation_id']
                              and g['workspace_id'] == target['workspace_id'] and g['capability'] == request['capability']), None)
                if grant is None or grant['state'] != 'approved':
                    changes.append(dict(plugin_id=target['plugin_id'], workspace_id=target['workspace_id'], capability=request['capability'], action='grant'))
    request = dict(operation_type=operation_type, requested={}, targets=targets, permission_changes=changes,
                   operation_id=operation_id, created_at=created_at, bindings=document['state'].get('bindings', []))
    # New native feature plans use the complete lifecycle even when the queue
    # is currently empty. Historical short journals remain recognizable.
    from .contracts import plan_hash
    from .plans import _display
    bundle=prepare_document({**document, 'request': request}, catalog)
    bundle['plan']['backup']['required']=True
    bundle['plan_hash']=plan_hash(bundle['plan'])
    bundle['display']=_display(bundle['plan'],bundle['operation_lock'])
    return bundle


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
    targets = [dict(installation_id=installation_id(site, plugin_id), site_id=site_id, workspace_id=workspace,
                    plugin_id=plugin_id, action='install') for workspace in sorted(workspace_ids)]
    return prepare_current_install_targets(document, sites, catalog, activation_targets=targets,
                                           operation_id=operation_id, created_at=created_at)
