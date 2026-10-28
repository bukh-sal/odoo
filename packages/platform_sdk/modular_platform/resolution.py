"""Pure release resolution using resolvelib and static operator-reviewed metadata.

No network, imports of plugin/wheel code, builds or installation take place.
Catalog/trust verification precedes this module; execution rechecks it later.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import copy
import re

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name
from packaging.version import Version
from resolvelib import AbstractProvider, BaseReporter, Resolver
from resolvelib.resolvers import ResolutionImpossible, ResolutionTooDeep

from .contracts import ContractError, api_range, normalize_manifest, package_version, resolve_ui


class PlanningError(ContractError):
    pass


@dataclass(frozen=True)
class Need:
    key: str
    specifier: str = ''
    origin: str = 'requested'
    extras: frozenset[str] = frozenset()
    service: tuple[str, int, str] | None = None


@dataclass(frozen=True)
class Candidate:
    key: str
    version: str
    digest: str
    extras: frozenset[str] = frozenset()
    metadata: dict = field(default_factory=dict, compare=False, hash=False)


def _service_matches(candidate, service):
    service_id, major, specifier = service
    return [item for item in candidate.metadata['manifest']['services']['provides']
            if item['id'] == service_id and int(item['api_version'].split('.')[0]) == major
            and Version(item['api_version']) in api_range(specifier, major)]


def dependency_order(graph):
    """Deterministic dependency-first order, with the actual cycle in errors."""
    visited, active, result = set(), [], []

    def visit(key):
        if key in active:
            cycle = active[active.index(key):] + [key]
            raise PlanningError('Hard dependency cycle: ' + ' -> '.join(cycle))
        if key in visited:
            return
        active.append(key)
        for child in sorted(graph[key]):
            if child not in graph:
                raise PlanningError('Missing hard dependency: ' + key + ' -> ' + child)
            visit(child)
        active.pop()
        visited.add(key)
        result.append(key)

    for key in sorted(graph):
        visit(key)
    return result


class _Provider(AbstractProvider):
    def __init__(self, plugins, wheels, environment, locked, update, choices, core_python):
        self.environment, self.locked, self.update, self.choices = environment, locked, update, choices
        self.candidates = {}
        for descriptor in plugins:
            manifest = normalize_manifest(descriptor['manifest'])
            plugin = manifest['plugin']['id']
            candidate = Candidate('plugin:' + plugin, manifest['plugin']['version'], descriptor['digest'],
                                  metadata={**descriptor, 'manifest': manifest})
            self.candidates.setdefault(candidate.key, []).append(candidate)
        for descriptor in wheels:
            name = canonicalize_name(descriptor['name'])
            if not re.fullmatch('sha256:[0-9a-f]{64}', descriptor['digest']):
                raise PlanningError('Python metadata requires an immutable source digest')
            # Reviewed metadata is bound either to a qualified runtime image or
            # an independently inspected wheel. A source-build command is invalid.
            if descriptor.get('kind') not in ('runtime_distribution', 'wheel'):
                raise PlanningError('Python planning requires static wheel/runtime metadata')
            if descriptor.get('kind') == 'wheel' and not set(descriptor.get('tags', [])) & set(environment['accepted_wheel_tags']):
                continue
            if Version(environment['markers']['python_full_version']) not in SpecifierSet(descriptor.get('requires_python', '')):
                continue
            candidate = Candidate('python:' + name, str(Version(descriptor['version'])), descriptor['digest'], metadata=descriptor)
            self.candidates.setdefault(candidate.key, []).append(candidate)
        # A catalog snapshot must not hide same-version byte replacement. Python
        # metadata is also preselected by target tags/source policy, not file order.
        for key, values in self.candidates.items():
            identities = {}
            for candidate in values:
                if candidate.version in identities and identities[candidate.version] != candidate.digest:
                    raise PlanningError('Ambiguous same-version source: ' + key)
                identities[candidate.version] = candidate.digest

    def identify(self, requirement_or_candidate):
        return requirement_or_candidate.key

    def get_preference(self, identifier, resolutions, candidates, information, backtrack_causes):
        return (0 if identifier.startswith('plugin:') else 1, identifier)

    def find_matches(self, identifier, requirements, incompatibilities):
        needs = list(requirements[identifier])
        excluded = list(incompatibilities[identifier])
        extras = frozenset(extra for need in needs for extra in need.extras)
        candidates = [replace(item, extras=extras) for item in self.candidates.get(identifier, [])]
        candidates = [item for item in candidates if item not in excluded
                      and all(self.is_satisfied_by(need, item) for need in needs)]
        candidates.sort(key=lambda item: (Version(item.version), item.digest), reverse=True)
        locked = self.locked.get(identifier)
        if locked:
            # Downgrades are never ordinary resolution. Restoring a checkpoint
            # is a distinct executor operation, not a solver flag.
            candidates = [item for item in candidates if Version(item.version) >= Version(locked['version'])]
            if identifier not in self.update:
                candidates.sort(key=lambda item: not (item.version == locked['version'] and item.digest == locked['digest']))
        return candidates

    def is_satisfied_by(self, requirement, candidate):
        if requirement.key != candidate.key or Version(candidate.version) not in SpecifierSet(requirement.specifier):
            return False
        if not requirement.extras <= candidate.extras:
            return False
        if candidate.key.startswith('plugin:'):
            manifest = candidate.metadata['manifest']
            if Version(self.environment['platform_version']) not in SpecifierSet(manifest['compatibility']['platform']):
                return False
            if manifest['runtime']['kind'] == 'native' and Version(self.environment['markers']['python_full_version']) not in SpecifierSet(manifest['runtime']['python']):
                return False
            if requirement.service and not _service_matches(candidate, requirement.service):
                return False
        return True

    def python_need(self, raw, origin, extras=frozenset()):
        requirement = Requirement(raw)
        if requirement.url:
            raise PlanningError('Direct URL Python requirements need separately reviewed static metadata')
        if requirement.marker and not any(requirement.marker.evaluate({**self.environment['markers'], 'extra': extra}) for extra in (set(extras) | {''})):
            return None
        return Need('python:' + canonicalize_name(requirement.name), str(requirement.specifier), origin, frozenset(requirement.extras))

    def provider(self, candidate, requirement, *, optional=False):
        plugin = candidate.metadata['manifest']['plugin']['id']
        alias = requirement['alias']
        service = (requirement['id'], requirement['contract_major'], requirement['version'])
        explicit = self.choices.get((plugin, alias))
        eligible = {item.key[7:] for key, values in self.candidates.items() if key.startswith('plugin:')
                    for item in values if self.is_satisfied_by(Need(item.key, service=service), item)}
        if explicit:
            if explicit not in eligible:
                raise PlanningError('Explicit service provider does not satisfy ' + plugin + ':' + alias)
            return explicit
        if optional:
            # Optional providers never enter the required dependency graph.
            return None
        if len(eligible) > 1:
            raise PlanningError('Explicit provider binding required for ' + plugin + ':' + alias + ': ' + ', '.join(sorted(eligible)))
        return next(iter(eligible), '__missing_provider__')

    def get_dependencies(self, candidate):
        result = []
        if candidate.key.startswith('python:'):
            for raw in candidate.metadata.get('requires_dist', []):
                need = self.python_need(raw, candidate.key + '==' + candidate.version, candidate.extras)
                if need:
                    result.append(need)
            return result
        manifest = candidate.metadata['manifest']
        origin = candidate.key + '==' + candidate.version
        for plugin, specifier in manifest['dependencies']['plugins'].items():
            result.append(Need('plugin:' + plugin, specifier, origin))
        if manifest['runtime']['kind'] == 'native':
            for raw in manifest['runtime']['python_dependencies']:
                need = self.python_need(raw, origin)
                if need:
                    result.append(need)
        for requirement in manifest['services']['requires']:
            if requirement.get('optional', False):
                continue
            provider = self.provider(candidate, requirement)
            service = (requirement['id'], requirement['contract_major'], requirement['version'])
            result.append(Need('plugin:' + provider, '', origin + ':' + requirement['alias'], service=service))
        return result


def resolve_release(catalog, python_metadata, environment, requested, *, locked=None, update=(),
                    provider_choices=None, core_python=(), site_requirements=None):
    """Resolve the WHOLE deployment, retaining installed roots and fixed sites.

    `locked` maps plugin:/python: identifiers to exact version/digest records.
    `requested` maps plugin IDs to PEP440 constraints; `update` explicitly permits
    preferring newer versions. All metadata is data, supplied by reviewed callers.
    """
    environment = copy.deepcopy(environment)
    required_markers = set(default_environment())
    if not isinstance(environment.get('markers'), dict) or not required_markers <= environment['markers'].keys():
        raise PlanningError('Complete target marker environment is required; host defaults are forbidden')
    if environment.get('native_runtime') != 'odoo-19' or not isinstance(environment.get('accepted_wheel_tags'), list):
        raise PlanningError('Explicit supported target runtime and wheel tags are required')
    locked = copy.deepcopy(locked or {})
    choices = dict(provider_choices or {})
    update = {value if value.startswith(('plugin:', 'python:')) else 'plugin:' + value for value in update}
    provider = _Provider(copy.deepcopy(catalog), copy.deepcopy(python_metadata), environment, locked, update, choices, core_python)
    roots = [Need('plugin:' + key, specifier) for key, specifier in sorted(requested.items())]
    roots.extend(Need(key, '', 'currently installed') for key in sorted(locked) if key.startswith('plugin:') and key[7:] not in requested)
    roots.extend(Need(key, '', 'currently locked Python runtime') for key in sorted(locked) if key.startswith('python:'))
    for raw in core_python:
        need = provider.python_need(raw, 'platform Python runtime')
        if need:
            roots.append(need)
    for site, requirements in sorted((site_requirements or {}).items()):
        roots.extend(Need('plugin:' + key, specifier, 'shared-runtime site ' + site) for key, specifier in sorted(requirements.items()))
    try:
        mapping = Resolver(provider, BaseReporter()).resolve(roots, max_rounds=10_000).mapping
    except ResolutionImpossible as error:
        causes = sorted({item.requirement.key + item.requirement.specifier + ' from ' + item.requirement.origin for item in error.causes})
        kind = 'Python dependency conflict' if any(item.requirement.key.startswith('python:') for item in error.causes) else 'Plugin dependency conflict'
        raise PlanningError(kind + ': ' + '; '.join(causes)) from error
    except ResolutionTooDeep as error:
        raise PlanningError('Resolution complexity limit; no partial solution may be applied') from error
    plugins = {key[7:]: item for key, item in mapping.items() if key.startswith('plugin:')}
    graph = {key: list(item.metadata['manifest']['dependencies']['plugins']) for key, item in plugins.items()}
    order = dependency_order(graph)
    manifests = [plugins[key].metadata['manifest'] for key in order]
    ui = resolve_ui(manifests)
    addons = {}
    for plugin, item in plugins.items():
        manifest = item.metadata['manifest']
        if manifest['runtime']['kind'] == 'native':
            addon = manifest['runtime']['addon_name']
            if addon in addons:
                raise PlanningError('Conflicting native addon ownership: ' + addon)
            addons[addon] = plugin
    core_addons = set(environment.get('core_addons', []))
    for plugin, item in plugins.items():
        native = item.metadata.get('native_manifest')
        if item.metadata['manifest']['runtime']['kind'] != 'native':
            continue
        if not native:
            raise PlanningError('Validated static native manifest required for ' + plugin)
        manifest = item.metadata['manifest']
        expected = {plugins[key].metadata['manifest']['runtime']['addon_name']
                    for key in graph[plugin] if plugins[key].metadata['manifest']['runtime']['kind'] == 'native'}
        native_deps = set(native['depends'])
        if not expected <= native_deps or not native_deps <= expected | core_addons or (not expected and not native_deps & core_addons):
            raise PlanningError('Native dependency mapping disagrees for ' + plugin)
        for target in manifest['data']['extension_targets']:
            if not any(target in plugins[key].metadata['manifest']['data']['models'] for key in graph[plugin]):
                raise PlanningError('Native extension target lacks a hard owner dependency: ' + plugin + ' -> ' + target)
    bindings, optional = [], []
    for plugin in order:
        candidate = plugins[plugin]
        manifest = candidate.metadata['manifest']
        for target, specifier in sorted(manifest['integrations']['optional'].items()):
            optional.append({'consumer': plugin, 'provider': target,
                             'available': target in plugins and Version(plugins[target].version) in SpecifierSet(specifier)})
        for requirement in manifest['services']['requires']:
            service = (requirement['id'], requirement['contract_major'], requirement['version'])
            eligible = {key: value for key, value in plugins.items() if _service_matches(value, service)}
            selected = choices.get((plugin, requirement['alias']))
            if selected and selected not in eligible:
                raise PlanningError('Selected provider is not installed/compatible: ' + plugin + ':' + requirement['alias'])
            if not selected and len(eligible) > 1:
                raise PlanningError('Explicit provider binding required for ' + plugin + ':' + requirement['alias'])
            selected = selected or next(iter(eligible), None)
            if not selected:
                if not requirement.get('optional', False):
                    raise PlanningError('Unresolved required service alias: ' + plugin + ':' + requirement['alias'])
                continue
            api = max(_service_matches(eligible[selected], service), key=lambda value: Version(value['api_version']))
            bindings.append({'consumer': plugin, 'alias': requirement['alias'], 'provider': selected,
                'service_id': service[0], 'contract_major': service[1], 'api_version': api['api_version'],
                'optional': requirement.get('optional', False)})
    reasons = {}
    for need in roots + [need for item in mapping.values() for need in provider.get_dependencies(item)]:
        reasons.setdefault(need.key, set()).add(need.origin + ' ' + need.specifier)
    return {'target_environment': environment, 'plugins': [plugins[key].metadata for key in order], 'native_order': [plugins[key].metadata['manifest']['runtime']['addon_name'] for key in order if plugins[key].metadata['manifest']['runtime']['kind'] == 'native'],
            'python': [{**item.metadata, 'extras': sorted(item.extras)} for key, item in sorted(mapping.items()) if key.startswith('python:')],
            'bindings': bindings, 'optional_integrations': optional, 'ui': ui,
            'reasons': {key: sorted(value) for key, value in sorted(reasons.items())}}


def dependent_closure(installed, targets, *, cascade=False):
    """Hard/native + selected required-service dependents for suspend/removal."""
    targets = set(targets)
    known = {item['manifest']['plugin']['id']: item for item in installed}
    if not targets <= known.keys():
        raise PlanningError('Unknown installed target')
    closure = set(targets)
    while True:
        additions = {key for key, item in known.items() if key not in closure
                     and (set(item['manifest']['dependencies']['plugins']) & closure
                          or set(item.get('required_providers', [])) & closure)}
        if not additions:
            break
        closure.update(additions)
    if closure != targets and not cascade:
        raise PlanningError('Explicit dependent cascade required: ' + ', '.join(sorted(closure - targets)))
    return sorted(closure)
