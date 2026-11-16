"""Current resource revocations survive a checkpoint footprint; source proof."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'packages/platform_sdk'))
from modular_platform.resource_authority_recovery import (
    canonical_snapshot, canonical_observation, reconcile, authority_select,
    resource_proof, verify_resource_proof, overlay_sql)
from modular_platform.integration_grant_recovery import grant_proof, verify_proof, reconciled_authority, proof_binding
from modular_platform.native_auth_recovery import read_query
from modular_platform.restore_executor import RestoreExecutor, AUTHORITY_SELECT, canonical_authority, authority_sql
from modular_platform.operator_os import OperatorError


def ident(n):
    return f'00000000-0000-4000-8000-{n:012d}'


def policy(**changes):
    return dict(policy_id=ident(1), installation_id=ident(2), plugin_id='dev.test.records',
        workspace_id=ident(3), model_name='test.record', resource_id=ident(4), owner_id=ident(5),
        state='active', revision=1, member_capabilities=['record.read']) | changes


def grant(**changes):
    return dict(policy_id=ident(1), principal_id=ident(6), capability='record.write', state='approved') | changes


def snapshot(*, policies=None, grants=None):
    return dict(schema_version=1, policies=[policy()] if policies is None else policies,
                grants=[grant()] if grants is None else grants)


def authority(resources):
    value = dict(principals=[], memberships=[], operators=[], integration_grants=[])
    if resources is not None:
        value['resource_access'] = resources
    return canonical_authority(value)


class ResourceAuthorityRecoveryTests(unittest.TestCase):
    def test_exact_schema_canonicalization_is_nonmutating_and_order_neutral(self):
        raw = snapshot(policies=[policy(member_capabilities=['record.write', 'record.read'])],
                       grants=[grant(principal_id=ident(8)), grant()])
        before = copy.deepcopy(raw); value = canonical_snapshot(raw)
        self.assertEqual(raw, before)
        self.assertEqual(value['policies'][0]['member_capabilities'], ['record.read', 'record.write'])
        self.assertEqual(value['grants'][0], grant())
        self.assertEqual(canonical_snapshot(snapshot(policies=[], grants=[])), snapshot(policies=[], grants=[]))

    def test_unknown_partial_duplicate_or_malformed_identity_refuses(self):
        for raw in (None, {}, dict(snapshot(), extra=True), dict(snapshot(), schema_version=True),
                    snapshot(policies=[policy(), policy()]), snapshot(grants=[grant(), grant()]),
                    snapshot(grants=[grant(policy_id=ident(99))])):
            with self.subTest(raw=raw), self.assertRaises(OperatorError): canonical_snapshot(raw)
        for key, value in dict(policy_id='bad', resource_id=ident(4).upper()+'A', plugin_id='test',
                model_name='test;drop', revision=True, state='enabled', member_capabilities=['record.read']*2).items():
            with self.subTest(key=key), self.assertRaises(OperatorError): canonical_snapshot(snapshot(policies=[policy(**{key:value})]))

    def test_absent_schema_only_for_observed_pre_feature_core(self):
        raw = dict(schema=dict(policy=False, grant=False, core_version='19.0.0.2.56'), policies=[], grants=[])
        self.assertIsNone(canonical_observation(raw))
        for change in (dict(policy=True), dict(grant=True), dict(core_version='19.0.0.2.57'),
                       dict(core_version=None), dict(core_version='19.0.0.2.58')):
            with self.subTest(change=change), self.assertRaises(OperatorError):
                canonical_observation(dict(raw, schema=raw['schema'] | change))
        complete = dict(schema=dict(policy=True, grant=True, core_version='19.0.0.2.57'),
                        policies=[policy()], grants=[grant()])
        self.assertEqual(canonical_observation(complete), snapshot())
        with self.assertRaises(OperatorError):
            canonical_observation(dict(complete, schema=complete['schema'] | dict(core_version='19.0.0.2.56')))

    def test_fixed_query_skips_absent_tables_before_parsing_in_one_native_snapshot(self):
        present = authority_select(AUTHORITY_SELECT, present=True)
        absent = authority_select(AUTHORITY_SELECT, present=False)
        self.assertIn('FROM mp_resource_policy r', present)
        self.assertNotIn('FROM mp_resource_policy', absent)
        self.assertNotIn('FROM mp_resource_grant', absent)
        sql = read_query(present, authority_without_resources=absent)
        self.assertEqual(sql.count('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY'), 1)
        self.assertEqual(sql.count('ROLLBACK;'), 1)
        self.assertEqual(sql.count('\\if :mp_restore_has_resources'), 2)
        self.assertIn("AND to_regclass('public.mp_resource_grant')", sql)
        self.assertNotIn('UPDATE ', sql)

    def test_revocation_defaults_and_tombstones_win_without_creating_content(self):
        checkpoint = snapshot(); before = copy.deepcopy(checkpoint)
        current = snapshot(policies=[policy(revision=4, member_capabilities=[])], grants=[grant(state='revoked')])
        result = reconcile(checkpoint, current)
        self.assertEqual(result, current)
        self.assertEqual(checkpoint, before)
        missing = reconcile(checkpoint, snapshot(policies=[], grants=[]))
        self.assertEqual(missing['policies'], [policy(state='revoked', revision=2, member_capabilities=[])])
        self.assertEqual(missing['grants'], [grant(state='revoked')])

    def test_new_current_share_only_applies_to_checkpoint_resources(self):
        current = snapshot(policies=[policy(revision=2), policy(policy_id=ident(10), resource_id=ident(11))],
            grants=[grant(), grant(principal_id=ident(7)), grant(policy_id=ident(10))])
        result = reconcile(snapshot(), current)
        self.assertEqual(result['policies'], [policy(revision=2)])
        self.assertEqual(result['grants'], [grant(), grant(principal_id=ident(7))])
        self.assertEqual(reconcile(snapshot(policies=[], grants=[]), current), snapshot(policies=[], grants=[]))

    def test_unchanged_revision_cannot_hide_permission_mutation(self):
        for current in (snapshot(grants=[]), snapshot(grants=[grant(state='revoked')]),
                        snapshot(grants=[grant(), grant(principal_id=ident(7))]),
                        snapshot(policies=[policy(member_capabilities=[])])):
            with self.subTest(current=current), self.assertRaises(OperatorError): reconcile(snapshot(), current)
        self.assertEqual(reconcile(snapshot(), snapshot()), snapshot())
        with self.assertRaises(OperatorError):
            reconcile(snapshot(policies=[policy(revision=4)]), snapshot())

    def test_replaced_owner_or_binding_never_relabels_an_existing_policy(self):
        for key, value in dict(owner_id=ident(90), workspace_id=ident(90), installation_id=ident(90),
                plugin_id='dev.test.other', model_name='test.other', resource_id=ident(90)).items():
            with self.subTest(key=key), self.assertRaises(OperatorError):
                reconcile(snapshot(), snapshot(policies=[policy(**{key:value}, revision=2)]))
        with self.assertRaises(OperatorError):
            reconcile(snapshot(), snapshot(policies=[policy(policy_id=ident(90))], grants=[]))

    def test_existing_proof_binds_resources_source_checkpoint_and_resume(self):
        source = snapshot(policies=[policy(revision=2)], grants=[grant(state='revoked')])
        decision = dict(operation_id='operation', plan_hash='plan', checkpoint_digest='checkpoint', authority=authority(source))
        proof = grant_proof(decision, [], resource_checkpoint=snapshot())
        self.assertEqual(verify_proof(proof, decision), proof)
        self.assertEqual(reconciled_authority(decision, proof)['resource_access'], source)
        self.assertEqual(proof_binding(proof)['resource_authority_digest'], proof['resource_access']['expected_digest'])
        for field in proof['resource_access']:
            changed = copy.deepcopy(proof); changed['resource_access'][field] = None
            with self.subTest(field=field), self.assertRaises(OperatorError): verify_proof(changed, decision)
        changed = copy.deepcopy(decision); changed['authority']['resource_access']['policies'][0]['revision'] += 1
        with self.assertRaises(OperatorError): verify_proof(proof, changed)
        with self.assertRaises(OperatorError): verify_proof({k:v for k,v in proof.items() if k!='resource_access'}, decision)

    def test_legacy_proof_bytes_unchanged_and_pre_feature_checkpoint_has_no_resources(self):
        decision = dict(operation_id='op', plan_hash='plan', checkpoint_digest='cp', authority=authority(None))
        legacy = grant_proof(decision, [])
        self.assertNotIn('resource_access', legacy)
        self.assertNotIn('resource_access', reconciled_authority(decision, legacy))
        with self.assertRaises(OperatorError): grant_proof(decision, [], resource_checkpoint=snapshot())
        new = dict(decision, authority=authority(snapshot()))
        proof = grant_proof(new, [], resource_checkpoint=None)
        self.assertNotIn('resource_access', reconciled_authority(new, proof))

    def test_overlay_uses_fixed_tables_and_exact_public_bindings_without_app_sql(self):
        query = authority_sql(authority(snapshot()))
        self.assertIn('UPDATE mp_resource_policy', query)
        self.assertIn('r.owner_id=p.id AND p.public_id=a.owner_id', query)
        self.assertIn('r.model_name=a.model_name AND r.resource_id=a.resource_id', query)
        self.assertIn('ON CONFLICT(policy_id,principal_id,capability)', query)
        self.assertNotIn('DELETE FROM', query)
        self.assertNotIn('INSERT INTO mp_resource_policy', query)
        self.assertNotIn('UPDATE test_record', query)
        self.assertNotIn('resource_policy', authority_sql(authority(None)))

    def test_actual_observer_strips_only_verified_old_schema_and_requires_observation(self):
        native_auth = dict(users=[dict(id=1,login='fixture',active=True,password=None,totp_secret=None,
                                      totp_last_counter=0,groups=[])], passkeys=[])
        old = dict(schema=dict(policy=False,grant=False,core_version='19.0.0.2.56'), policies=[], grants=[])
        recovery = object.__new__(RestoreExecutor); recovery.observer = Mock()
        value = dict(authority=dict(principals=[],memberships=[],operators=[],integration_grants=[],resource_access=old), native_auth=native_auth)
        with patch('modular_platform.restore_executor._run', return_value=json.dumps(value).encode()) as run:
            actual, _ = recovery._authority('owned')
            self.assertNotIn('resource_access', actual)
            self.assertIn(b'mp_restore_has_resources', run.call_args.kwargs['input'])
        del value['authority']['resource_access']
        with patch('modular_platform.restore_executor._run', return_value=json.dumps(value).encode()), self.assertRaises(OperatorError):
            recovery._authority('owned')

    def test_completion_denies_resource_mismatch_before_any_registry_or_dispatch(self):
        source = snapshot(policies=[policy(revision=2)], grants=[grant(state='revoked')])
        decision = dict(operation_id='op',plan_hash='plan',checkpoint_digest='cp',authority=authority(source))
        proof = grant_proof(decision,[],resource_checkpoint=snapshot())
        recovery = object.__new__(RestoreExecutor)
        recovery._grant_proof = Mock(return_value=proof)
        wrong = reconciled_authority(decision,proof); wrong['resource_access']['grants'][0]['state']='approved'
        recovery._authority = Mock(return_value=(wrong,None)); recovery._supported_effects=Mock()
        recovery._before_registry_restore=Mock()
        with self.assertRaisesRegex(OperatorError,'Restored authority differs'):
            recovery._complete_restore(decision,exact_hash='hash',locks=None,directory=Path('.'),
                checkpoint=Path('.'),manifest={},fresh='fresh',private_native_auth=None)
        recovery._supported_effects.assert_not_called(); recovery._before_registry_restore.assert_not_called()

    def test_resume_rechecks_the_resource_proof_and_recorded_binding(self):
        from modular_platform.plans import data_digest
        decision = dict(operation_id='op',plan_hash='plan',checkpoint_digest='cp',authority=authority(snapshot()))
        proof = grant_proof(decision,[],resource_checkpoint=snapshot())
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            (directory/'decision.json').write_text(json.dumps(dict(decision=decision,hash=data_digest(decision))))
            (directory/'integration-grants.json').write_text(json.dumps(proof))
            recovery=object.__new__(RestoreExecutor); recovery.store=Mock(); recovery._bundle=Mock(return_value={'plan_hash':'plan'})
            result=proof_binding(proof)
            self.assertEqual(recovery._resume_grant_proof(directory,'op',result),proof)
            for field in ('resource_authority_policy','resource_authority_digest'):
                changed=dict(result); changed.pop(field)
                with self.subTest(field=field),self.assertRaises(OperatorError):
                    recovery._resume_grant_proof(directory,'op',changed)


if __name__ == '__main__': unittest.main()
