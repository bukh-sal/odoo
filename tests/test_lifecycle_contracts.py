"""Native-uninstall impact is a bounded observation, never execution authority."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/platform_sdk'))
from modular_platform.contracts import ContractError, validate, validate_operations_view, plan_hash
from modular_platform.plans import data_digest

EXAMPLES = ROOT / 'packages/contracts/examples/v1'


def example(name='lifecycle-impact'):
    if name == 'lifecycle-impact-unknown':
        return json.loads((EXAMPLES / 'lifecycle-impact/unknown.json').read_text(encoding='utf-8'))
    return json.loads((EXAMPLES / (name + '.json')).read_text(encoding='utf-8'))


class LifecycleContracts(unittest.TestCase):
    def test_dispatch_extension_requires_complete_recognized_schema(self):
        for name in ('dispatch-base', 'dispatch-events'):
            value = json.loads((EXAMPLES / f'lifecycle-impact/{name}.json').read_text())
            validate('lifecycle-impact', value)
            self.assertEqual(value['impact_digest'], data_digest(value['impact']))
            for tables in ([], ['mp_job'], value['impact']['dispatch']['tables'] + ['unknown_queue']):
                wrong = copy.deepcopy(value)
                wrong['impact']['dispatch']['tables'] = tables
                with self.subTest(name=name, tables=tables), self.assertRaises(ContractError):
                    validate('lifecycle-impact', wrong)

    def test_known_unknown_examples_and_old_consumers(self):
        for name in ('lifecycle-impact', 'lifecycle-impact-unknown'):
            value = example(name)
            validate('lifecycle-impact', value)
            self.assertEqual(value['impact_digest'], data_digest(value['impact']))
        for name in ('operations-view', 'operations-view-status'):
            validate_operations_view(example(name))
        for name in ('manager-view', 'manager-view-details', 'manager-view-upload'):
            validate('manager-view', example(name))
        self.assertEqual(plan_hash(example('plan')), (EXAMPLES / 'plan.sha256').read_text().strip())

    def test_authority_commands_credentials_and_unknown_keys_rejected(self):
        for at in ('root', 'impact', 'plugin', 'field'):
            for key in ('approved', 'command', 'password', 'operator_id', 'database', 'keep_data'):
                value = example()
                target = value if at == 'root' else value['impact'] if at == 'impact' else value['impact']['plugins'][0] if at == 'plugin' else value['impact']['fields'][0]
                target[key] = True
                with self.subTest(at=at, key=key), self.assertRaises(ContractError):
                    validate('lifecycle-impact', value)

    def test_cannot_claim_non_destructive_keep_data_or_untrusted_execution(self):
        for key, changed in [('destructive', False), ('requires_backup', False),
                             ('native_code_fully_trusted', False), ('artifact_action', 'remove'),
                             ('database_action', 'retain'), ('completeness', 'all_effects'),
                             ('control_authority', 'application')]:
            value = example()
            value[key] = changed
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate('lifecycle-impact', value)

    def test_unknown_relation_mapping_cannot_invent_counts_or_columns(self):
        for key, changed in [('relation', 'guessed_table'), ('column', 'guessed_column'),
                             ('non_null_records', 3), ('unknown_reason', None)]:
            value = example('lifecycle-impact-unknown')
            value['impact']['fields'][0][key] = changed
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate('lifecycle-impact', value)
        value = example()
        value['impact']['fields'][0]['non_null_records'] = None
        with self.assertRaises(ContractError):
            validate('lifecycle-impact', value)

    def test_database_names_are_data_not_lowercase_native_addon_identifiers(self):
        value = example()
        value['impact']['fields'][0].update(relation='Custom Table', column='MixedCase')
        value['impact']['constraints'] = [{'relation': 'Custom Table', 'name': 'MixedCase_Check', 'definition': "CHECK (value <> '<untrusted text>')"}]
        validate('lifecycle-impact', value)
        value['impact']['fields'][0]['relation'] = 'bad\x00name'
        with self.assertRaises(ContractError):
            validate('lifecycle-impact', value)

    def test_limits_protocol_identifiers_and_dispatch_consistency(self):
        for key, changed in [('schema_version', 2), ('plan_hash', 'sha256:' + 'a' * 64 + '\n'),
                             ('operation_id', '00000000-0000-0000-0000-000000000500\n')]:
            value = example()
            value[key] = changed
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate('lifecycle-impact', value)
        for count in (-1, 9007199254740992):
            value = example()
            value['impact']['fields'][0]['non_null_records'] = count
            with self.assertRaises(ContractError):
                validate('lifecycle-impact', value)
        value = example()
        value['impact']['fields'] *= 1001
        with self.assertRaises(ContractError):
            validate('lifecycle-impact', value)
        value = example()
        value['impact']['dispatch']['tables'] = ['mp_job']
        with self.assertRaises(ContractError):
            validate('lifecycle-impact', value)
        value['impact']['dispatch']['state'] = 'unsupported'
        validate('lifecycle-impact', value)


if __name__ == '__main__':
    unittest.main()
