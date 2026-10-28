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


def validate(name, value):
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
