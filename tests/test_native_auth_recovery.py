"""Secret-free native-auth review binding and strict private overlay inputs."""
import copy,json,secrets,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.native_auth_recovery import canonical_native_auth,public_binding,overlay_sql,read_query,POLICY,SCHEMA_FIELDS
from modular_platform.operator_os import OperatorError

class NativeAuthRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.secret=secrets.token_urlsafe(32);self.totp=secrets.token_hex(20)
  self.value=dict(users=[dict(id=1,login="o'brien",active=True,password=self.secret,totp_secret=self.totp,totp_last_counter=10,groups=[3,2])],passkeys=[dict(id=1,name='fixture',credential_identifier=secrets.token_urlsafe(24),public_key='public-key-fixture',sign_count=1,create_uid=1,write_uid=1,create_date=None,write_date=None)])
 def test_review_contains_only_policy_and_digest_and_never_secret_material(self):
  binding=public_binding(self.value);self.assertEqual(set(binding),{'native_auth_policy','native_auth_digest'});self.assertEqual(binding['native_auth_policy'],POLICY);self.assertNotIn(self.secret,json.dumps(binding));self.assertNotIn(self.totp,json.dumps(binding))
 def test_each_current_credential_permission_and_counter_change_invalidates_review(self):
  baseline=public_binding(self.value)
  for field,value in [('password',None),('totp_secret',None),('totp_last_counter',11),('groups',[2]),('active',False)]:
   with self.subTest(field=field):
    changed=copy.deepcopy(self.value);changed['users'][0][field]=value;self.assertNotEqual(baseline,public_binding(changed))
  for field,value in [('sign_count',2),('credential_identifier','different-key')]:
   changed=copy.deepcopy(self.value);changed['passkeys'][0][field]=value;self.assertNotEqual(baseline,public_binding(changed))
  changed=copy.deepcopy(self.value);changed['passkeys']=[];self.assertNotEqual(baseline,public_binding(changed))
 def test_ordering_is_not_authority_drift_and_input_is_unchanged(self):
  before=copy.deepcopy(self.value);other=copy.deepcopy(self.value);other['users'][0]['groups'].reverse();self.assertEqual(public_binding(other),public_binding(before));self.assertEqual(self.value,before)
 def test_malformed_unknown_or_duplicate_private_records_fail_with_redacted_error(self):
  invalid=[{},None,dict(self.value,unexpected=self.secret)]
  for field,value in [('id',True),('groups',[2,2]),('totp_last_counter',-1),('arbitrary_shell',self.secret)]:
   changed=copy.deepcopy(self.value);changed['users'][0][field]=value;invalid.append(changed)
  changed=copy.deepcopy(self.value);changed['users']*=2;invalid.append(changed)
  changed=copy.deepcopy(self.value);changed['passkeys'][0]['unreviewed_extension']=self.secret;invalid.append(changed)
  for candidate in invalid:
   with self.assertRaises(OperatorError) as raised:canonical_native_auth(candidate)
   self.assertNotIn(self.secret,str(raised.exception))
 def test_private_SQL_handles_quotes_and_invalidates_remembered_device_material(self):
  sql=overlay_sql(self.value);self.assertIn("o''brien",sql);self.assertIn('DELETE FROM auth_totp_device',sql);self.assertIn('Native identity or group footprint requires explicit reconciliation',sql);self.assertIn('totp_last_counter',sql)
 def minimal(self):
  value=copy.deepcopy(self.value);value['passkeys']=[];value['users'][0].update(totp_secret=None,totp_last_counter=None);value['schema']={k:False for k in SCHEMA_FIELDS};return value
 def test_full_schema_retains_legacy_canonical_value_and_digest(self):
  explicit=dict(copy.deepcopy(self.value),schema={k:True for k in SCHEMA_FIELDS})
  self.assertEqual(canonical_native_auth(explicit),canonical_native_auth(self.value));self.assertEqual(public_binding(explicit),public_binding(self.value))
 def test_absent_features_are_distinct_from_present_but_empty(self):
  minimal=self.minimal();present=copy.deepcopy(minimal);present.pop('schema')
  self.assertNotEqual(public_binding(minimal),public_binding(present));self.assertEqual(canonical_native_auth(minimal)['schema'],{k:False for k in SCHEMA_FIELDS})
  changed=copy.deepcopy(minimal);changed['users'][0]['password']=None;self.assertNotEqual(public_binding(minimal),public_binding(changed))
 def test_partial_unknown_or_nonboolean_schema_refuses(self):
  for change in ({'totp_secret':True},{'totp_device':True},{'passkeys':1},{'foreign':False}):
   value=self.minimal();value['schema'].update(change)
   with self.subTest(change=change),self.assertRaises(OperatorError):canonical_native_auth(value)
 def test_absent_features_cannot_hide_credential_material(self):
  for field,value in [('totp_secret',self.totp),('totp_last_counter',1)]:
   changed=self.minimal();changed['users'][0][field]=value
   with self.assertRaises(OperatorError):canonical_native_auth(changed)
  changed=self.minimal();changed['passkeys']=copy.deepcopy(self.value['passkeys'])
  with self.assertRaises(OperatorError):canonical_native_auth(changed)
 def test_overlay_binds_schema_before_writes_and_skips_only_absent_features(self):
  sql=overlay_sql(self.minimal())
  self.assertLess(sql.index('Native authentication schema changed'),sql.index('UPDATE res_users'))
  self.assertNotIn('totp_secret=a.totp_secret',sql);self.assertNotIn('DELETE FROM auth_passkey_key',sql);self.assertNotIn('DELETE FROM auth_totp_device',sql)
  self.assertIn('password=a.password',sql);self.assertIn('DELETE FROM res_groups_users_rel',sql)
  totp=self.minimal();totp['schema'].update(totp_secret=True,totp_last_counter=True,totp_device=True)
  self.assertIn('DELETE FROM auth_totp_device',overlay_sql(totp));self.assertNotIn('DELETE FROM auth_passkey_key',overlay_sql(totp))
  passkeys=self.minimal();passkeys['schema']['passkeys']=True;passkeys['passkeys']=copy.deepcopy(self.value['passkeys'])
  self.assertIn('DELETE FROM auth_passkey_key',overlay_sql(passkeys));self.assertNotIn('DELETE FROM auth_totp_device',overlay_sql(passkeys))
 def test_read_query_selects_fixed_optional_relation_inside_one_readonly_snapshot(self):
  sql=read_query('SELECT 1;')
  self.assertTrue(sql.startswith('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;'));self.assertTrue(sql.endswith('ROLLBACK;'))
  self.assertIn('\\if :mp_restore_has_passkeys',sql);self.assertNotIn('u.totp_secret',sql)
  self.assertNotIn('FROM auth_passkey_key',sql.split('\\else\n',1)[1])

if __name__=='__main__':unittest.main()
