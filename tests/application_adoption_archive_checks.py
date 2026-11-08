"""Actual immutable app-set dependency refusals; no site mutation or code import."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'packages/platform_sdk')]
from modular import configuration
from modular_platform.artifacts import ArtifactValidator, TrustPolicy
from modular_platform.catalog import Catalog
from modular_platform.deployment import inspect_image
from modular_platform.projection import runtime_inputs
from modular_platform.resolution import resolve_release, PlanningError
from package_composition import validate_composition, validate_dependencies


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--operator', required=True, type=Path)
    p.add_argument('--candidate', required=True, type=Path)
    p.add_argument('--old-tasks', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args(); assert not a.output.exists()
    receipt = json.loads(a.candidate.read_text(encoding='utf8'))
    assert receipt['state'] == 'verified'
    runtime = inspect_image(receipt['image_id'])
    catalog = Catalog(a.operator/'catalog', configuration(a.operator/'trust.json'), readonly=True)
    snapshot = catalog.snapshot(); selected, environment, provenance = runtime_inputs(runtime, snapshot)
    raw = a.old_tasks.read_bytes(); digest = 'sha256:'+hashlib.sha256(raw).hexdigest()
    old = ArtifactValidator(TrustPolicy(approved_digests=frozenset([digest]))).verify(a.old_tasks, expected_digest=digest).descriptor()
    assert old['manifest']['plugin']['id'] == 'dev.aurora.tasks' and old['manifest']['plugin']['version'] == '0.2.2'
    selected = [row for row in selected if row['manifest']['plugin']['id'] in {'dev.aurora.projects', 'dev.aurora.tasks', 'dev.aurora.projects_tasks'}]
    assert len(selected) == 3
    extension_version=next(r['manifest']['plugin']['version'] for r in selected if r['manifest']['plugin']['id']=='dev.aurora.projects_tasks')
    def solve(rows, requested=None, env=None):
        return resolve_release(rows, [], env or environment, requested or {'dev.aurora.projects_tasks': '=='+extension_version})
    solution = solve(selected)
    assert {r['manifest']['plugin']['id']: r['manifest']['plugin']['version'] for r in solution['plugins']} == {
        'dev.aurora.projects': '0.1.1', 'dev.aurora.tasks': '0.2.3', 'dev.aurora.projects_tasks': extension_version}
    project = [r for r in selected if r['manifest']['plugin']['id'] == 'dev.aurora.projects']
    assert len(solve(project, {'dev.aurora.projects': '==0.1.1'})['plugins']) == 1
    cases = [
        ('missing Projects', [r for r in selected if r not in project], None, None),
        ('missing Tasks', [r for r in selected if r['manifest']['plugin']['id'] != 'dev.aurora.tasks'], None, None),
        ('incompatible actual Tasks0.2.2', [r for r in selected if r['manifest']['plugin']['id'] != 'dev.aurora.tasks']+[old], None, None),
        ('unsupported Projects0.2.0 root', selected, {'dev.aurora.projects': '==0.2.0'}, None),
        ('unqualified platform0.1.50', selected, None, dict(environment, platform_version='0.1.50')),
    ]
    refused = []
    for name, rows, roots, env in cases:
        before = copy.deepcopy((rows, roots, env))
        try:
            solve(rows, roots, env)
        except PlanningError as error:
            assert 'Plugin dependency conflict' in str(error), (name, str(error))
            refused.append(name)
        else:
            raise AssertionError('Accepted '+name)
        assert (rows, roots, env) == before
    manifests = [r['manifest'] for r in selected]
    native = {r['manifest']['runtime']['addon_name']: r['native_manifest'] for r in selected}
    validate_dependencies(manifests, native, set(environment['core_addons']))
    raws = [catalog.path(r['digest']).read_bytes() for r in selected]
    validate_composition(raws)
    result = dict(result='passed', checks=8, image_id=receipt['image_id'], inventory_digest=receipt['inventory_digest'],
        artifacts={r['manifest']['plugin']['id']: r['digest'] for r in selected}, actual_old_tasks=digest,
        accepted=['Full three-app dependency closure', 'Independent Projects-only closure', 'Actual native/package ownership and dependency declarations'],
        refused=refused, site_mutation=False, native_code_imported=False,
        bounds='Pure planning with actual verified archive bytes and actual image marker environment; actual installation/recovery has separate evidence.')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
