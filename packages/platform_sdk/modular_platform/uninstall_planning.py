"""Current-image site-wide uninstall: data-only nomination, never authority."""
from __future__ import annotations

import copy

from .contracts import plan_hash
from .lifecycle_impact import impact_view
from .planning_cli import prepare_document
from .plans import _display, check_bundle, data_digest
from .resolution import PlanningError


def validate_uninstall_targets(document, sites, impact, targets, *, operation_id, created_at):
    # Validate the strict standalone impact through its DTO; this synthetic hash
    # is not an executable proposal or approval. The final hash is made below.
    impact_view(impact, operation_id=operation_id, plan_hash='sha256:' + '0' * 64, observed_at=created_at)
    if impact['dispatch']['state'] != 'not_present':
        raise PlanningError('Native uninstall requires the G6 durable dispatch drain adapter')
    site = next((s for s in sites if s['site_id'] == impact['site_id']), None)
    if site is None:
        raise PlanningError('Native uninstall site is outside the observed deployment')
    entries = {row['plugin_id']: row for row in document['state']['release_lock']['plugins']}
    natives = {row['addon']: row for row in site['native_modules']}
    plugins = impact['plugins']
    if (len({row['plugin_id'] for row in plugins}) != len(plugins)
            or len({row['native_addon'] for row in plugins}) != len(plugins)
            or {row['native_addon'] for row in plugins} != set(impact['native_closure'])
            or not set(impact['requested_addons']) <= set(impact['native_closure'])):
        raise PlanningError('Native uninstall impact has an inconsistent dependent closure')
    expected = []
    for row in plugins:
        entry = entries.get(row['plugin_id'])
        installation = next((i for i in site['installations'] if i['installation_id'] == row['installation_id']), None)
        if (entry is None or installation is None or entry['runtime'] != 'native'
                or installation['plugin_id'] != row['plugin_id'] or installation['metadata_state'] != 'installed'
                or (entry['native_addon'], entry['version'], entry['digest']) != (
                    row['native_addon'], row['version'], row['artifact_digest'])
                or (installation['version'], installation['digest']) != (row['version'], row['artifact_digest'])
                or natives.get(row['native_addon'], {}).get('state') != 'installed'
                or natives[row['native_addon']]['version'] != entry['native_version']):
            raise PlanningError('Native uninstall impact differs from current installation/source identity')
        scopes = sorted(f['workspace_id'] for f in site['features'] if f['installation_id'] == row['installation_id'])
        observed = sorted(i['workspace_id'] for i in document['state']['installations']
                          if i['site_id'] == site['site_id'] and i['installation_id'] == row['installation_id']
                          and i['plugin_id'] == row['plugin_id'] and i['state'] == 'installed')
        if scopes != sorted(row['workspace_ids']) or scopes != observed or len(scopes) != len(set(scopes)):
            raise PlanningError('Native uninstall impact omits an affected workspace, including suspended scopes')
        expected.extend(dict(installation_id=row['installation_id'], site_id=site['site_id'], workspace_id=workspace,
                             plugin_id=row['plugin_id'], action='uninstall') for workspace in scopes)
    order = lambda row: (row['site_id'], row['workspace_id'], row['plugin_id'], row['installation_id'])
    if not isinstance(targets, list) or sorted(targets, key=order) != sorted(expected, key=order):
        raise PlanningError('Native uninstall targets must equal the complete approved impact closure')


def prepare_current_image_uninstall(document, sites, catalog, *, impact, targets, operation_id, created_at):
    validate_uninstall_targets(document, sites, impact, targets, operation_id=operation_id, created_at=created_at)
    site = next(s for s in sites if s['site_id'] == impact['site_id'])
    installations = {p['installation_id']: p for p in impact['plugins']}
    revocations = []
    for grant in site.get('grants', []):
        plugin = installations.get(grant['installation_id'])
        if plugin is None or grant['state'] != 'approved':
            continue
        if grant['workspace_id'] not in plugin['workspace_ids']:
            raise PlanningError('Native uninstall grant scope requires explicit reconciliation')
        revocations.append(dict(plugin_id=plugin['plugin_id'], workspace_id=grant['workspace_id'],
                                capability=grant['capability'], action='revoke'))
    bundle = prepare_document({**document, 'request': dict(operation_type='uninstall', requested={},
        targets=copy.deepcopy(targets), permission_changes=revocations, operation_id=operation_id, created_at=created_at)}, catalog)
    lock = bundle['operation_lock']
    lock['native_uninstall_impact'] = copy.deepcopy(impact)
    lock['known_unknowns'].extend(impact['warnings'])
    bundle['plan']['dependency_lock_digest'] = data_digest(lock)
    bundle['plan_hash'] = plan_hash(bundle['plan'])
    bundle['display'] = _display(bundle['plan'], lock)
    check_bundle(bundle, document['state'])
    return bundle
