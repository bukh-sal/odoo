"""Checkpoint grant identity is retained; current platform authority wins."""
import copy
import sys
import unittest
from pathlib import Path
import json
import tempfile
from contextlib import nullcontext
from unittest.mock import Mock,patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'))
from modular_platform.integration_grant_recovery import (POLICY,canonical_grants,
    restored_grants,grant_proof,verify_proof,reconciled_authority)
from modular_platform.restore_executor import RestoreExecutor,canonical_authority,authority_sql
from modular_platform.operator_os import OperatorError


def grant(**changes):
    return dict(installation_id='00000000-0000-4000-8000-000000000001',
        plugin_id='dev.local.documents',workspace_id='00000000-0000-4000-8000-000000000002',
        capability='documents.files:read',state='approved',policy_version=1)|changes


class IntegrationGrantRecoveryTests(unittest.TestCase):
    def test_canonical_explicit_empty_and_missing_authority(self):
        value=dict(principals=[],memberships=[],operators=[],integration_grants=[])
        self.assertEqual(canonical_authority(value)['integration_grants_policy'],POLICY)
        self.assertNotIn('integration_grants_policy',value)
        with self.assertRaises(OperatorError):canonical_authority({})
        for rows in (None,{},[{}],[grant(),grant()]):
            with self.subTest(rows=rows),self.assertRaises(OperatorError):canonical_grants(rows)

    def test_malformed_rows_never_become_authority(self):
        cases=dict(installation_id='not-uuid',workspace_id='00000000-0000-4000-8000-00000000000A',
            plugin_id='documents',capability='read',state='suspended',policy_version=True)
        for key,value in cases.items():
            with self.subTest(key=key),self.assertRaises(OperatorError):canonical_grants([grant(**{key:value})])
        for value in (0,-1,1.0,None):
            with self.assertRaises(OperatorError):canonical_grants([grant(policy_version=value)])
        with self.assertRaises(OperatorError):canonical_grants([grant(extra='unreviewed')])

    def test_matching_current_state_version_and_checkpoint_only_revoke(self):
        checkpoint=[grant(),grant(capability='documents.files:write')]
        before=copy.deepcopy(checkpoint)
        current=[grant(state='revoked',policy_version=3),grant(capability='documents.files:delete')]
        rows=restored_grants(checkpoint,current)
        self.assertEqual(rows,[grant(state='revoked',policy_version=3),grant(capability='documents.files:write',state='revoked')])
        self.assertEqual(checkpoint,before)
        self.assertEqual(restored_grants([grant(state='revoked')],[grant(policy_version=4)]),[grant(policy_version=4)])
        self.assertEqual(restored_grants([],current),[])
        self.assertEqual(restored_grants([grant()],[]),[grant(state='revoked')])

    def test_different_stable_scope_never_matches(self):
        for change in (dict(plugin_id='dev.local.other'),dict(capability='documents.files:write'),
                dict(installation_id='00000000-0000-4000-8000-000000000003'),
                dict(workspace_id='00000000-0000-4000-8000-000000000004')):
            with self.subTest(change=change):
                self.assertEqual(restored_grants([grant()],[grant(**change)]),[grant(state='revoked')])

    def test_proof_binds_operation_plan_source_checkpoint_and_expected_rows(self):
        decision=dict(operation_id='operation',plan_hash='exact-plan',checkpoint_digest='checkpoint',authority=dict(integration_grants=[grant(state='revoked')],memberships=['unchanged']))
        proof=grant_proof(decision,[grant()])
        self.assertEqual(verify_proof(proof,decision),proof)
        self.assertEqual(reconciled_authority(decision,proof)['memberships'],['unchanged'])
        for field in proof:
            changed=copy.deepcopy(proof);changed[field]=None
            with self.subTest(field=field),self.assertRaises((OperatorError,TypeError)):
                verify_proof(changed,decision)
        for field in ('operation_id','plan_hash','checkpoint_digest','authority'):
            changed=copy.deepcopy(decision)
            if field=='authority':changed[field]['integration_grants']=[]
            else:changed[field]='other'
            with self.assertRaises(OperatorError):verify_proof(proof,changed)

    def test_sql_is_fixed_overlay_without_grant_insert_or_delete(self):
        query=authority_sql(dict(principals=[],memberships=[],operators=[],integration_grants=[grant()]))
        self.assertIn("UPDATE mp_plugin_grant SET state='revoked'",query)
        self.assertIn('i.public_id=a.installation_id',query)
        self.assertIn('i.plugin_id=a.plugin_id',query)
        self.assertIn('g.capability=a.capability',query)
        self.assertNotIn('INSERT INTO mp_plugin_grant',query)
        self.assertNotIn('DELETE FROM mp_plugin_grant',query)

    def test_actual_execute_captures_checkpoint_proof_before_overlay_and_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);op='00000000-0000-4000-8000-000000000010'
            checkpoint=root/'checkpoints'/op;checkpoint.mkdir(parents=True)
            for name,body in [('manifest.json',b'{}'),('database.dump',b'dump'),('filestore.tar.gz',b'filestore')]:
                (checkpoint/name).write_bytes(body)
            native=Mock();native.store.root=root;native.store.policy={'allow_noninteractive':True}
            native.config=dict(sites=[dict(database='source')]);native.observer._container.return_value='db'
            native.store.bundle.return_value=dict(plan=dict(deployment_id='deployment',site_ids=['site']))
            native._child.return_value=(['docker','run','image'],'name')
            source=canonical_authority(dict(principals=[],memberships=[],operators=[],integration_grants=[grant(state='revoked',policy_version=4)]))
            checkpoint_authority=canonical_authority(dict(principals=[],memberships=[],operators=[],integration_grants=[grant(),grant(capability='documents.files:write')]))
            decision=dict(operation_id=op,plan_hash='plan',checkpoint_digest='checkpoint',
                authority=source,managed_workers=[],fresh_database='fresh',
                restore_configuration={'generation':1},restored_release_lock={'generation':1,'core_inventory_digest':'inventory'},review={'expires_at':'future'})
            recovery=RestoreExecutor(native);recovery._restore_state=Mock(return_value={})
            private=dict(users=[dict(id=1,login='fixture',active=True,password=None,totp_secret=None,totp_last_counter=0,groups=[])],passkeys=[])
            recovery._authority=Mock(side_effect=[(source,private),(checkpoint_authority,private)])
            recovery._complete_restore=Mock(return_value='verified')
            timeline=[];directory=root/'recoveries'/op
            def run(args,**kwargs):
                if args[:3]==['docker','exec','db'] and 'createdb' in args:timeline.append('create')
                elif 'pg_restore' in args:timeline.append('dump')
                elif '--single-transaction' in args:
                    timeline.append('overlay')
                    proof=json.loads((directory/'integration-grants.json').read_text())
                    self.assertEqual(proof['expected_grants'],restored_grants(checkpoint_authority['integration_grants'],source['integration_grants']))
                    self.assertIn(b"UPDATE mp_plugin_grant SET state='revoked'",kwargs['input'])
                return b''
            native._private_command.side_effect=lambda *a,**k:timeline.append('filestore')
            with patch('modular_platform.restore_executor.OperationLocks',return_value=nullcontext(Mock())),patch('modular_platform.restore_executor.RecoveryReviews'),patch('modular_platform.restore_executor._run',side_effect=run):
                self.assertEqual(recovery.execute(decision,exact_hash='hash',noninteractive=True),'verified')
            self.assertEqual(timeline,['create','dump','filestore','overlay'])
            recovery._complete_restore.assert_called_once()
            self.assertEqual(recovery._authority.call_args_list[0].args,('source',))
            self.assertEqual(recovery._authority.call_args_list[1].args,('fresh',))

    def test_completion_refuses_wrong_grants_before_any_dispatch_or_startup(self):
        recovery=object.__new__(RestoreExecutor);recovery._grant_proof=Mock()
        decision=dict(operation_id='operation',plan_hash='plan',checkpoint_digest='checkpoint',
            authority=dict(integration_grants=[grant(state='revoked')]))
        recovery._grant_proof.return_value=grant_proof(decision,[grant()])
        recovery._authority=Mock(return_value=(dict(integration_grants=[grant()]),None))
        recovery._supported_effects=Mock()
        with self.assertRaisesRegex(OperatorError,'Restored authority differs'):
            recovery._complete_restore(decision,exact_hash='hash',locks=None,directory=Path('.'),
                checkpoint=Path('.'),manifest={},fresh='fresh',private_native_auth=None)
        recovery._supported_effects.assert_not_called()

    def test_source_grant_change_while_draining_refuses_before_database_creation(self):
        with tempfile.TemporaryDirectory() as folder:
            native=Mock();native.store.root=Path(folder);native.store.policy={'allow_noninteractive':True}
            native.config={'sites':[dict(database='source')]}
            native.store.bundle.return_value=dict(plan=dict(deployment_id='deployment',site_ids=['site']))
            recovery=RestoreExecutor(native);recovery._restore_state=Mock(return_value={})
            reviewed=dict(integration_grants=[grant()])
            recovery._authority=Mock(return_value=(dict(integration_grants=[grant(state='revoked')]),None))
            decision=dict(operation_id='operation',authority=reviewed,managed_workers=[],fresh_database='fresh',review={'expires_at':'future'})
            with patch('modular_platform.restore_executor.OperationLocks',return_value=nullcontext(Mock())),patch('modular_platform.restore_executor.RecoveryReviews'),patch('modular_platform.restore_executor._run') as run:
                with self.assertRaisesRegex(OperatorError,'authority changed while draining'):
                    recovery.execute(decision,exact_hash='hash',noninteractive=True)
            run.assert_not_called();native._private_command.assert_not_called()


if __name__=='__main__':unittest.main()
