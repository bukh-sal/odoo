import copy
import json
from pathlib import Path
import sys
import hashlib
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/platform_sdk'))
from modular_platform.lifecycle_impact import (check_impact_view, impact_view, native_closure,
                                               static_relations, verified_archive_sources)
from modular_platform.resolution import PlanningError
from modular_platform.contracts import ContractError
from modular_platform.plans import data_digest


class LifecycleImpactTests(unittest.TestCase):
    def descriptor(self, addon, depends=()):
        return {'version': '0.1.0', 'manifest': {'runtime': {'kind': 'native', 'addon_name': addon}},
                'native_manifest': {'depends': list(depends)}}

    def test_actual_declared_reference_mapping_and_extension(self):
        root = Path(__file__).resolve().parents[1] / 'platform_addons'
        paths = ['mp_example_notes/models.py', 'mp_example_notes_labels/models.py',
                 'mp_example_canvas/models.py', 'mp_identity/models/scoped.py']
        relations = static_relations({p: (root / p).read_bytes() for p in paths})
        self.assertEqual(relations['mp.example.note'], 'mp_example_note')
        self.assertEqual(relations['mp.example.canvas.board'], 'mp_example_canvas_board')
        self.assertIsNone(relations['mp.workspace.scoped'])

    def test_custom_table_never_guessed_from_model_name(self):
        source = "class A(models.Model):\n _name='x.a'\n _table='Actual Mixed Table'\n"
        self.assertEqual(static_relations({'a.py': source}), {'x.a': 'Actual Mixed Table'})
        extension = "class B(models.Model):\n _inherit='x.a'\n _table='OtherTable'\n"
        self.assertEqual(static_relations({'a.py': source, 'b.py': extension}), {'x.a': None})
        for table in ("compute_table()", "'x'*64", "'bad\\x00table'"):
            with self.subTest(table=table):
                self.assertIsNone(static_relations({'a.py': source.replace("'Actual Mixed Table'", table)})['x.a'])

    def test_unresolved_view_inheritance_and_python_bases_are_unknown(self):
        base = "class A(models.Model):\n _name='x.a'\n"
        for extra in (" _auto=False\n", " _inherit=['missing.mixin']\n", " _inherits={'x.b':'b_id'}\n", " _table_query='SELECT 1'\n"):
            with self.subTest(extra=extra):
                self.assertIsNone(static_relations({'a.py': base + extra})['x.a'])
        self.assertIsNone(static_relations({'a.py': base.replace('models.Model', 'CustomBase')})['x.a'])
        nested = (base + " _inherit=['x.mixin']\nclass M(models.AbstractModel):\n _name='x.mixin'\n"
                  " _inherit=['x.parent']\nclass P(models.AbstractModel):\n _name='x.parent'\n _table='CustomParent'\n")
        self.assertIsNone(static_relations({'a.py': nested})['x.a'])

    def test_dynamic_definition_and_duplicate_root_fail_closed_without_execution(self):
        source = "raise RuntimeError('must never execute')\nclass A(models.Model):\n _name='x.a'\n"
        self.assertEqual(static_relations({'a.py': source}), {'x.a': 'x_a'})
        self.assertIsNone(static_relations({'a.py': source, 'b.py': "class B(models.Model):\n _name=dynamic_name()\n"})['x.a'])
        self.assertIsNone(static_relations({'a.py': source, 'b.py': source})['x.a'])
        conditional = source + " if enabled:\n  _table='DifferentTable'\n"
        self.assertIsNone(static_relations({'a.py': conditional})['x.a'])

    def test_archive_and_individual_source_bytes_are_both_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'verified.mplug'
            raw = b"class A(models.Model):\n _name='x.a'\n"
            name = 'backend/odoo_addons/example/models.py'
            with zipfile.ZipFile(path, 'w') as archive: archive.writestr('org.example.test/' + name, raw)
            descriptor = self.descriptor('example')
            descriptor['manifest']['plugin'] = {'id': 'org.example.test'}
            descriptor.update(digest='sha256:' + hashlib.sha256(path.read_bytes()).hexdigest(),
                              inventory={name: hashlib.sha256(raw).hexdigest()})
            self.assertEqual(verified_archive_sources(path, descriptor), {'example/models.py': raw})
            descriptor['inventory'][name] = '0'*64
            with self.assertRaises(PlanningError): verified_archive_sources(path, descriptor)
            descriptor['digest'] = 'sha256:'+'0'*64
            with self.assertRaises(PlanningError): verified_archive_sources(path, descriptor)

    def test_closure_includes_all_installed_dependents_and_checks_both_graphs(self):
        descriptors = [self.descriptor('notes', ['core']), self.descriptor('labels', ['notes']), self.descriptor('canvas', ['core'])]
        modules = [dict(addon=n, state='installed', version='19.0.0.1.0', depends=d) for n, d in (
            ('core', []), ('notes', ['core']), ('labels', ['notes']), ('canvas', ['core']))]
        self.assertEqual(native_closure(['notes'], modules, descriptors), ['labels', 'notes'])
        self.assertEqual(native_closure(['labels'], modules, descriptors), ['labels'])
        bad = copy.deepcopy(modules); bad[2]['depends'] = ['canvas']
        with self.assertRaises(PlanningError): native_closure(['notes'], bad, descriptors)
        bad = copy.deepcopy(modules); bad[1]['version'] = '19.0.0.0.9'
        with self.assertRaisesRegex(PlanningError, 'installed version'): native_closure(['notes'], bad, descriptors)
        bad = modules + [dict(addon='unsupported', state='installed', depends=['notes'])]
        with self.assertRaises(PlanningError): native_closure(['notes'], bad, descriptors)
        for mutation in ('to upgrade', 'to remove', 'to install'):
            bad = copy.deepcopy(modules); bad[1]['state'] = mutation
            with self.assertRaises(PlanningError): native_closure(['notes'], bad, descriptors)
        for requested in ([], ['missing'], ['notes', 'notes'], ['notes\n']):
            with self.assertRaises(PlanningError): native_closure(requested, modules, descriptors)

    def test_count_drift_and_cross_operation_binding_are_detected(self):
        root = Path(__file__).resolve().parents[1]
        fixture = json.loads((root / 'packages/contracts/examples/v1/lifecycle-impact.json').read_text(encoding='utf8'))
        view = impact_view(fixture['impact'], operation_id=fixture['operation_id'], plan_hash=fixture['plan_hash'], observed_at=fixture['observed_at'])
        bound = dict(operation_id=fixture['operation_id'], plan_hash=fixture['plan_hash'], expected_impact_digest=fixture['impact_digest'])
        self.assertEqual(check_impact_view(view, **bound), fixture)
        changed = copy.deepcopy(view); changed['impact']['fields'][0]['non_null_records'] += 1
        with self.assertRaises(PlanningError): check_impact_view(changed, **bound)
        changed['impact_digest'] = data_digest(changed['impact'])
        with self.assertRaises(PlanningError): check_impact_view(changed, **bound)
        changed = copy.deepcopy(view); changed['operation_id'] = '00000000-0000-0000-0000-000000000999'
        with self.assertRaises(PlanningError): check_impact_view(changed, **bound)
        changed = copy.deepcopy(view); changed['impact']['extra_command'] = 'not allowed'
        with self.assertRaises(ContractError): check_impact_view(changed, **bound)


if __name__ == '__main__':
    unittest.main()
