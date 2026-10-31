"""Strict R1 boundary validation shared by CLI, gateway and build tooling."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import tomllib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import rfc8785
from jsonschema import Draft202012Validator, FormatChecker
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

CONTRACTS = Path(__file__).resolve().parents[2] / 'contracts' / 'v1'
PACKAGE_VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')
ERROR_STATUS = {
    'UNAUTHENTICATED': 401, 'FORBIDDEN': 403, 'NOT_FOUND': 404,
    'VALIDATION_FAILED': 400, 'CONFLICT': 409, 'DEPENDENCY_UNAVAILABLE': 503,
    'PLUGIN_SUSPENDED': 409, 'RATE_LIMITED': 429, 'DEADLINE_EXCEEDED': 504,
    'CANCELLED': 409, 'INTERNAL_ERROR': 500,
}
FORMAT_CHECKER = FormatChecker()


@FORMAT_CHECKER.checks('date-time', raises=ValueError)
def canonical_utc_datetime(value):
    # jsonschema's optional RFC3339 dependency is not installed by the minimal
    # runtime. Enforce this protocol's UTC profile with the standard library.
    if not isinstance(value,str): return True  # type is validated separately
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z',value):return False
    datetime.fromisoformat(value.replace('Z','+00:00'))
    return True


class ContractError(ValueError):
    """A safe author/operator-facing validation failure."""


def load_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError('Duplicate JSON property')
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: (_ for _ in ()).throw(ContractError('Nonfinite number')))
    except (TypeError, json.JSONDecodeError) as error:
        raise ContractError('Invalid JSON') from error


def _event_transport_limits(value):
    """Bound the new recursive DTO before schema traversal; no authority here."""
    def visit(item,depth):
        if depth>16:raise ContractError('Event transport exceeds JSON depth')
        if isinstance(item,dict):
            if len(item)>128 or any(not isinstance(key,str) for key in item):raise ContractError('Invalid event object')
            for child in item.values():visit(child,depth+1)
        elif isinstance(item,list):
            if len(item)>128:raise ContractError('Invalid event array')
            for child in item:visit(child,depth+1)
    visit(value,1)
    try:raw=rfc8785.dumps(value)
    except Exception:raise ContractError('Invalid event JSON') from None
    if len(raw)>65536:raise ContractError('Event message exceeds byte limit')
    if not isinstance(value,dict):return
    deliveries=value.get('deliveries',[]) if value.get('kind')=='poll_result' else []
    if isinstance(deliveries,list):
        for delivery in deliveries:
            event=delivery.get('event') if isinstance(delivery,dict) else None
            if isinstance(event,dict):
                if len(rfc8785.dumps(event))>16384:raise ContractError('Event exceeds byte limit')
                if event.get('topic')=='org.example.notes.changed' and isinstance(event.get('payload'),dict):
                    payload=event['payload']
                    if event.get('aggregate_id')!=payload.get('note_id') or event.get('aggregate_sequence')!=payload.get('revision'):
                        raise ContractError('Inconsistent Notes event identity/revision')
        for field in ['id','event']:
            ids=[d.get('id') if field=='id' else d.get('event',{}).get('id') for d in deliveries if isinstance(d,dict) and (field=='id' or isinstance(d.get('event'),dict))]
            if len(ids)!=len(set(str(ident) for ident in ids)):raise ContractError('Duplicate event delivery')
    receipts=value.get('receipts',[]) if value.get('kind')=='ack_request' else []
    if isinstance(receipts,list):
        ids=[r.get('delivery_id') for r in receipts if isinstance(r,dict)]
        if len(ids)!=len(set(str(ident) for ident in ids)):raise ContractError('Duplicate acknowledgement target')


def validate(name, value):
    if name=='event-transport':_event_transport_limits(value)
    schema = json.loads((CONTRACTS / (name + '.schema.json')).read_text())
    validator = Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(value), key=lambda e: str(e.path))
    if errors:
        # Avoid echoing values that may contain credentials or private content.
        path = '.'.join(map(str, errors[0].absolute_path)) or '<root>'
        raise ContractError(f'{name}: invalid field {path} ({errors[0].validator})')
    return value


def package_version(value):
    if not isinstance(value, str) or not PACKAGE_VERSION.fullmatch(value):
        raise ContractError('Expected canonical numeric X.Y.Z package version')
    return Version(value)


def native_version(value):
    package_version(value)
    return '19.0.' + value


def checked_path(value):
    if not isinstance(value, str) or '\\' in value or ':' in value or '\x00' in value:
        raise ContractError('Unsafe package path')
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ('', '.', '..') for part in value.split('/')):
        raise ContractError('Unsafe package path')
    return value


def api_range(value, major):
    # R1 service APIs use M.m. Restrict ranges to an auditable subset of PEP440;
    # package/Python dependency specifiers retain their full PEP440 meaning.
    exact = re.fullmatch(r'==([1-9][0-9]*)\.(0|[1-9][0-9]*)', value)
    bounded = re.fullmatch(r'>=([1-9][0-9]*)\.(0|[1-9][0-9]*),<([1-9][0-9]*)\.0', value)
    if not ((exact and int(exact[1]) == major) or (bounded and int(bounded[1]) == major and int(bounded[3]) == major + 1)):
        raise ContractError('Service range must select exactly one declared major')
    return SpecifierSet(value)


def normalize_manifest(source, *, core=False):
    """Parse TOML as data; no plugin Python, handlers or build imports."""
    raw = tomllib.loads(source) if isinstance(source, str) else copy.deepcopy(source)
    if not isinstance(raw, dict):
        raise ContractError('Expected manifest object')
    for section in ['plugin','compatibility','runtime','activation','dependencies','integrations','permissions','data','ui','services','upgrade','external_service','extensions']:
        if section in raw and not isinstance(raw[section], dict):
            raise ContractError('Expected manifest section object')
    raw.setdefault('dependencies', {'plugins': {}})
    raw.setdefault('integrations', {'optional': {}})
    raw.setdefault('permissions', {})
    raw['permissions'].setdefault('defines', {})
    raw['permissions'].setdefault('requests', [])
    raw.setdefault('services', {})
    raw['services'].setdefault('provides', [])
    raw['services'].setdefault('requires', [])
    raw.setdefault('ui', {'mode':'none','design':'standard','pages':[],'navigation':[]})
    raw['ui'].setdefault('pages', [])
    raw['ui'].setdefault('navigation', [])
    raw.setdefault('data', {'models':[],'extension_targets':[],'contributions':[]})
    raw['data'].setdefault('contributions', [])
    raw.setdefault('upgrade', {})
    raw['upgrade'].setdefault('transitions', [])
    for page in raw['ui']['pages']:
        page.setdefault('ui_api_major', 1)
    validate('manifest', raw)
    package_version(raw['plugin']['version'])
    if not core and (raw['plugin']['id'].startswith('org.modularplatform.') or raw['runtime'].get('addon_name','').startswith('mp_core_') or raw['runtime'].get('addon_name') in {'mp_identity','mp_compat','mp_core','mp_shell','mp_jobs'}):
        raise ContractError('Reserved platform namespace')
    SpecifierSet(raw['compatibility']['platform'])
    native = raw['runtime']['kind'] == 'native'
    if native:
        SpecifierSet(raw['runtime']['python'])
        for dependency in raw['runtime']['python_dependencies']:
            Requirement(dependency)
    for ranges in [raw['dependencies']['plugins'], raw['integrations']['optional']]:
        for spec in ranges.values():
            SpecifierSet(spec)
    aliases = set()
    for requirement in raw['services']['requires']:
        if requirement['alias'] in aliases:
            raise ContractError('Duplicate consumer-local service alias')
        aliases.add(requirement['alias'])
        api_range(requirement['version'], requirement['contract_major'])
    registrations = set()
    for provider in raw['services']['provides']:
        key = provider['id'], int(provider['api_version'].split('.')[0])
        if key in registrations:
            raise ContractError('Duplicate provider service/major')
        registrations.add(key)
        checked_path(provider['schema'])
        if native != ('handler' in provider):
            raise ContractError('Native handlers and remote providers have distinct registration paths')
        if native and not re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_.]*:[a-zA-Z_][a-zA-Z0-9_]*', provider['handler']):
            raise ContractError('Invalid handler declaration')
    page_ids, paths = set(), set()
    for page in raw['ui']['pages']:
        if page['id'] in page_ids or page['path'] in paths:
            raise ContractError('Duplicate page contribution')
        page_ids.add(page['id']); paths.add(page['path'])
        if (page['kind'] == 'native_view') != ('action_ref' in page) or (page['kind'] == 'custom') != ('entry_asset' in page):
            raise ContractError('Page renderer must have exactly its matching reference')
        if 'entry_asset' in page:
            checked_path(page['entry_asset'])
    if any(nav['page'] not in page_ids for nav in raw['ui']['navigation']):
        raise ContractError('Navigation references undeclared page')
    for kind in ['slots','contributions','commands']:
        ids=set()
        for item in raw['ui'].get(kind,[]):
            expected='slot' if kind=='slots' else 'action' if kind=='contributions' else 'command'
            if not item['id'].startswith(raw['plugin']['id']+':'+expected+':') or item['id'] in ids:
                raise ContractError('Duplicate or incorrectly owned UI contribution')
            ids.add(item['id'])
            for field in ['context_schema','input_schema']:
                if field in item:checked_path(item[field])
            if 'handler' in item and not item['handler'].startswith(raw['plugin']['id']+':'+expected+':'):
                raise ContractError('UI handler must be owned compiled code')
    if 'export_schema' in raw['data']:
        checked_path(raw['data']['export_schema'])
    for transition in raw['upgrade']['transitions']:
        if package_version(transition['from']) >= package_version(transition['to']):
            raise ContractError('Migration transition must increase')
        for script in transition['scripts']:
            checked_path(script['path'])
            expected = f"migrations/{native_version(transition['to'])}/{script['phase']}-"
            if not script['path'].startswith(expected) or not script['path'].endswith('.py'):
                raise ContractError('Migration path must use full native target version and phase')
    return raw


def resolve_ui(manifests):
    """Pure data validation/order shared by activation/planning; never import JS/Python."""
    plugins={}
    for source in manifests:
        manifest=normalize_manifest(source)
        ident=manifest['plugin']['id']
        if ident in plugins:raise ContractError('Duplicate plugin')
        plugins[ident]=manifest
    slots={};contributions={};commands={};owned={}
    for plugin,manifest in plugins.items():
        for dependency,specifier in manifest['dependencies']['plugins'].items():
            if dependency not in plugins or package_version(plugins[dependency]['plugin']['version']) not in SpecifierSet(specifier):
                raise ContractError('Missing or incompatible UI dependency')
        for declaration in manifest['data']['contributions']:
            key=declaration['kind'],declaration['id']
            if key in owned:raise ContractError('Conflicting owned data contribution')
            owned[key]=plugin
        for item in manifest['ui'].get('slots',[]):
            if item['id'] in slots:raise ContractError('Duplicate slot')
            slots[item['id']]={**item,'plugin_id':plugin}
        for item in manifest['ui'].get('commands',[]):
            if item['id'] in commands:raise ContractError('Duplicate command')
            commands[item['id']]={**item,'plugin_id':plugin}
    for plugin,manifest in plugins.items():
        for item in manifest['ui'].get('contributions',[]):
            slot=slots.get(item['slot_id'])
            if not slot or slot['major']!=item['slot_major']:
                if item['optional']:continue
                raise ContractError('Required slot missing or incompatible')
            if slot['plugin_id']!=plugin and slot['plugin_id'] not in manifest['dependencies']['plugins']:
                raise ContractError('Slot contribution requires a hard provider dependency')
            if item['id'] in contributions:raise ContractError('Duplicate contribution')
            contributions[item['id']]={**item,'plugin_id':plugin}
    ordered=[];remaining=dict(contributions)
    while remaining:
        for item in remaining.values():
            if any(dependency not in contributions or contributions[dependency]['slot_id']!=item['slot_id'] for dependency in item['after']):
                raise ContractError('Unknown or cross-slot ordering dependency')
        ready=sorted((item for item in remaining.values() if not any(d in remaining for d in item['after'])),key=lambda item:(item['order'],item['plugin_id'],item['id']))
        if not ready:raise ContractError('UI contribution order cycle')
        for item in ready:ordered.append(item);del remaining[item['id']]
    return {'slots':slots,'contributions':ordered,'commands':commands}


def canonical_plan(plan):
    validate('plan', plan)
    def no_floats(value):
        if isinstance(value, float):
            raise ContractError('Plan numbers must be integers')
        if isinstance(value, dict):
            for child in value.values(): no_floats(child)
        if isinstance(value, list):
            for child in value: no_floats(child)
    no_floats(plan)
    for artifact in plan['artifacts']:
        if (artifact['runtime'] == 'native') != (artifact['native_addon'] is not None):
            raise ContractError('Artifact runtime/native mapping mismatch')
    # Array order is semantic. Planner sorts inventories before producing a plan;
    # approving code never silently sorts/re-writes an already reviewed plan.
    return rfc8785.dumps(plan)


def plan_hash(plan):
    return 'sha256:' + hashlib.sha256(canonical_plan(plan)).hexdigest()


def validate_operations_view(value):
    """Strict proposed UI data; never authenticates an OS approval or mirror."""
    validate('operations-view', value)
    if value['kind'] == 'prepared':
        plan=value['plan']
        if value['operation_id']!=plan['operation_id'] or value['plan_hash']!=plan_hash(plan):
            raise ContractError('Prepared operation identity/hash mismatch')
        if set(plan['site_ids'])!={item['site_id'] for item in value['targets']}:
            raise ContractError('Prepared operation site targets mismatch')
        if {(item['plugin_id'],item['action']) for item in plan['artifacts']}!={(item['plugin_id'],item['action']) for item in value['targets']}:
            raise ContractError('Prepared operation artifact targets mismatch')
        identities=[(item['installation_id'],item['workspace_id']) for item in value['targets']]
        if len(set(identities))!=len(identities):raise ContractError('Duplicate prepared feature target')
        if value['native_trusted_code']!=any(item['runtime']=='native' for item in plan['artifacts']):
            raise ContractError('Prepared native trust description mismatch')
        if value['restart_required']!=any(item['runtime']=='native' and item['action'] in ('install','upgrade','uninstall','remove') for item in plan['artifacts']):
            raise ContractError('Prepared restart description mismatch')
    elif value['kind']=='status':
        if value['source']=='application_request' and (value['state']!='awaiting_operator_approval' or value['approval_expires_at'] is not None):
            raise ContractError('Application request does not assert operator approval')
        if value['state']=='completed' and value['phase']!='completed':raise ContractError('Completed status phase mismatch')
        if value['state']=='approved' and value['approval_expires_at'] is None:raise ContractError('Approved mirror needs an expiry observation')
    elif value['kind']=='catalog':
        for item in value['items']:
            if item['trust_model']=='unsigned-development' and not item['warnings']:
                raise ContractError('Unsigned development catalog entry requires a visible warning')
    return value


def validate_binding(binding, requirement, provider):
    validate('binding', binding)
    desired = api_range(requirement['version'], requirement['contract_major'])
    if not (binding['alias'] == requirement['alias'] and binding['service_id'] == requirement['id'] == provider['id'] and binding['contract_major'] == requirement['contract_major'] == int(binding['api_version'].split('.')[0]) and binding['api_version'] == provider['api_version'] and Version(binding['api_version']) in desired and binding['provider_plugin_id'] == provider['plugin_id'] and binding['provider_installation_id'] == provider['installation_id']):
        raise ContractError('Binding target, major or version mismatch')
    return binding


def check_start_approval(plan, approval, *, operator_generation, now=None, maximum_lifetime=900):
    """Pure contract check, AFTER operator-store authentication. No execution.

    Store ownership, independent recomputation, reservation and mutation fencing
    remain executor requirements. An app-supplied record never authenticates it.
    """
    validate('approval', approval)
    now = now or datetime.now(timezone.utc)
    issued = datetime.fromisoformat(approval['issued_at'].replace('Z','+00:00'))
    expiry = datetime.fromisoformat(approval['expires_at'].replace('Z','+00:00'))
    if not (approval['state'] == 'approved' and approval['consumed_operation_id'] is None and issued <= now < expiry and 0 < (expiry-issued).total_seconds() <= maximum_lifetime):
        raise ContractError('Approval unavailable for starting operation')
    if approval['plan_hash'] != plan_hash(plan):
        raise ContractError('Approval plan hash mismatch')
    for field in ['operation_id','deployment_id','site_ids','policy_version','operator_authorization_generation']:
        if approval[field] != plan[field]:
            raise ContractError('Approval target or policy mismatch')
    if operator_generation != approval['operator_authorization_generation']:
        raise ContractError('Operator authorization changed')
    for field,needed in [('destructive',plan['destructive']),('trust_expansion',any(c['decision']=='approve' for c in plan['trust_changes'])),('permission_expansion',any(c['action']=='grant' for c in plan['permission_changes']))]:
        if needed and not approval['acknowledgments'][field]:
            raise ContractError('Required explicit acknowledgment missing')
    return approval
