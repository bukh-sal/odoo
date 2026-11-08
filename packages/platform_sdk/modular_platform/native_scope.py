"""Strict native site scope, distinct from every workspace feature scope."""
from .resolution import PlanningError


def require_site_entry(entry,selections=()):
    if (entry.get('runtime')!='native' or entry.get('activation',{}).get('scopes')!=['site']
            or entry.get('activation',{}).get('supports_feature_suspension') is not False
            or entry.get('permissions',{}).get('requests') or entry.get('provided_apis')
            or any(row['consumer']==entry['plugin_id'] or row['provider']==entry['plugin_id'] for row in selections)):
        raise PlanningError('Site-native scope requires a site-only native application without workspace grants or services')


def require_site_manifest(manifest):
    ui=manifest['ui']
    if (manifest['runtime']['kind']!='native' or manifest['activation']['scopes']!=['site']
            or manifest['activation']['supports_feature_suspension'] is not False
            or manifest['permissions']['requests'] or manifest['services']['requires'] or manifest['services']['provides']
            or any(ui.get(key) for key in ('pages','navigation','slots','commands','contributions'))):
        raise PlanningError('Site-native scope requires native views and no workspace grant/service/UI bindings')
