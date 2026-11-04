"""Explicit ADR0051 contract extension; does not update freeze hashes."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT/'packages/platform_sdk'))
from modular_platform.plans import data_digest
from modular_platform.dispatch_lifecycle import BASE, SCHEMA

path = ROOT/'packages/contracts/v1/lifecycle-impact.schema.json'
schema = json.loads(path.read_text())
dispatch = schema['properties']['impact']['properties']['dispatch']
assert dispatch['properties']['state']['enum'] == ['not_present', 'unsupported']
dispatch['properties']['state']['enum'].append('present_requires_fence')
dispatch['allOf'].append({
    'if': {'properties': {'state': {'const': 'present_requires_fence'}}},
    'then': {'properties': {'tables': {'oneOf': [
        {'const': sorted(BASE)}, {'const': sorted(SCHEMA)}]}}}})
path.write_text(json.dumps(schema, indent=2)+'\n', encoding='utf8')
example = json.loads((ROOT/'packages/contracts/examples/v1/lifecycle-impact.json').read_text())
for name, tables in [('dispatch-base', BASE), ('dispatch-events', SCHEMA)]:
    value = copy.deepcopy(example)
    value['impact']['dispatch'] = dict(state='present_requires_fence', tables=sorted(tables))
    value['impact_digest'] = data_digest(value['impact'])
    (ROOT/f'packages/contracts/examples/v1/lifecycle-impact/{name}.json').write_text(
        json.dumps(value, indent=2)+'\n', encoding='utf8')
