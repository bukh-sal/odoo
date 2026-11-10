"""Private native authentication reconciliation for the pinned R1 substrate.

Only a digest crosses into a recovery review. Password hashes/TOTP secrets are
read and overlaid through private operator stdin, never returned in status.
"""
import copy
import json

from .operator_os import OperatorError
from .plans import data_digest

POLICY = 'r1-current-native-auth-v1'
USER_FIELDS = {'id', 'login', 'active', 'password', 'totp_secret', 'totp_last_counter', 'groups'}
PASSKEY_FIELDS = {'id', 'name', 'credential_identifier', 'public_key', 'sign_count',
                  'create_uid', 'write_uid', 'create_date', 'write_date'}
SCHEMA_FIELDS = {'totp_secret', 'totp_last_counter', 'totp_device', 'passkeys'}
SCHEMA_SELECT = """SELECT jsonb_build_object(
 'totp_secret',EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='res_users' AND column_name='totp_secret'),
 'totp_last_counter',EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='res_users' AND column_name='totp_last_counter'),
 'totp_device',to_regclass('public.auth_totp_device') IS NOT NULL,
 'passkeys',to_regclass('public.auth_passkey_key') IS NOT NULL)"""


def _select(with_passkeys):
    # Fixed alternatives: a missing optional relation must not be parsed even
    # inside a SQL CASE. No caller-supplied identifiers or query fragments.
    passkeys = "COALESCE((SELECT jsonb_agg(to_jsonb(k) ORDER BY k.id) FROM auth_passkey_key k),'[]'::jsonb)" if with_passkeys else "'[]'::jsonb"
    return """SELECT jsonb_build_object(
 'users',COALESCE((SELECT jsonb_agg(jsonb_build_object(
   'id',u.id,'login',u.login,'active',u.active,'password',u.password,
   'totp_secret',to_jsonb(u)->'totp_secret','totp_last_counter',to_jsonb(u)->'totp_last_counter',
   'groups',COALESCE((SELECT jsonb_agg(g.gid ORDER BY g.gid) FROM res_groups_users_rel g WHERE g.uid=u.id),'[]'::jsonb)
 ) ORDER BY u.id) FROM res_users u),'[]'::jsonb),
 'passkeys',""" + passkeys + ", 'schema',(" + SCHEMA_SELECT + "))"


SELECT = _select(True)


def read_query(authority_select):
    # Both metadata and credentials come from one authoritative DB snapshot.
    def combined(native):
        return "SELECT jsonb_build_object('authority',(" + authority_select.strip().removesuffix(';') + "),'native_auth',(" + native + "));\n"
    # psql chooses fixed SQL before PostgreSQL parses the optional relation.
    # Schema presence and credentials stay in one readonly database snapshot.
    return ("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL statement_timeout='5s';\n"
            "SELECT (to_regclass('public.auth_passkey_key') IS NOT NULL) AS mp_restore_has_passkeys\n\\gset\n"
            "\\if :mp_restore_has_passkeys\n" + combined(SELECT) + "\\else\n" + combined(_select(False))
            + "\\endif\nROLLBACK;")


def canonical_native_auth(value):
    def reject():
        raise OperatorError('Unsupported native authentication snapshot; private reconciliation required')
    def ident(v, nullable=False):
        return v is None and nullable or type(v) is int and 0 < v < 2**31
    def text(v, nullable=False, maximum=65536):
        return v is None and nullable or isinstance(v, str) and len(v) <= maximum
    if not isinstance(value, dict) or set(value) not in ({'users', 'passkeys'}, {'users', 'passkeys', 'schema'}):
        reject()
    result = copy.deepcopy(value)
    schema = result.get('schema', {key: True for key in SCHEMA_FIELDS})
    if (not isinstance(schema, dict) or set(schema) != SCHEMA_FIELDS
            or any(type(v) is not bool for v in schema.values())
            or len({schema[k] for k in ('totp_secret', 'totp_last_counter', 'totp_device')}) != 1):
        reject()
    if not all(isinstance(result[k], list) for k in ('users', 'passkeys')) or not result['users']:
        reject()
    for user in result['users']:
        if (not isinstance(user, dict) or set(user) != USER_FIELDS or not ident(user['id'])
                or not text(user['login']) or not user['login'] or type(user['active']) is not bool
                or not text(user['password'], True) or not text(user['totp_secret'], True)
                or user['totp_last_counter'] is not None and (type(user['totp_last_counter']) is not int or user['totp_last_counter'] < 0)
                or not isinstance(user['groups'], list) or not all(ident(g) for g in user['groups'])
                or len(set(user['groups'])) != len(user['groups'])):
            reject()
        user['groups'].sort()
        if not schema['totp_secret'] and (user['totp_secret'] is not None or user['totp_last_counter'] is not None):
            reject()
    if len({u['id'] for u in result['users']}) != len(result['users']):
        reject()
    for key in result['passkeys']:
        if (not isinstance(key, dict) or set(key) != PASSKEY_FIELDS or not ident(key['id'])
                or not all(text(key[k], True) for k in ['name', 'credential_identifier', 'public_key', 'create_date', 'write_date'])
                or not all(ident(key[k], True) for k in ['create_uid', 'write_uid'])
                or key['sign_count'] is not None and (type(key['sign_count']) is not int or key['sign_count'] < 0)):
            reject()
    if len({k['id'] for k in result['passkeys']}) != len(result['passkeys']):
        reject()
    if not schema['passkeys'] and result['passkeys']:
        reject()
    if all(schema.values()):
        result.pop('schema', None)  # Retain the original full-auth v1 digest.
    else:
        result['schema'] = schema
    result['users'].sort(key=lambda u: u['id'])
    result['passkeys'].sort(key=lambda k: k['id'])
    return result


def public_binding(value):
    return {'native_auth_policy': POLICY, 'native_auth_digest': data_digest(canonical_native_auth(value))}


def overlay_sql(value):
    value = canonical_native_auth(value)
    payload = json.dumps(value).replace("'", "''")
    schema = value.get('schema', {key: True for key in SCHEMA_FIELDS})
    schema_json = json.dumps(schema)
    # Fixed identifiers and typed JSON records only. Do not log this SQL/input.
    return "SET LOCAL standard_conforming_strings=on; CREATE TEMP TABLE restore_native_auth(payload jsonb); INSERT INTO restore_native_auth VALUES ('" + payload + "'::jsonb);\n" + """
DO $$ BEGIN
 IF (""" + SCHEMA_SELECT + ") <> '" + schema_json + "'::jsonb THEN RAISE EXCEPTION 'Native authentication schema changed; explicit reconciliation required'; END IF;\n" + """
 IF EXISTS(SELECT id,login FROM res_users EXCEPT SELECT (u->>'id')::int,u->>'login' FROM restore_native_auth r,jsonb_array_elements(r.payload->'users') u)
 OR EXISTS(SELECT (u->>'id')::int,u->>'login' FROM restore_native_auth r,jsonb_array_elements(r.payload->'users') u EXCEPT SELECT id,login FROM res_users)
 OR EXISTS(SELECT 1 FROM restore_native_auth r,jsonb_array_elements(r.payload->'users') u,jsonb_array_elements(u->'groups') g LEFT JOIN res_groups current_group ON current_group.id=g::text::int WHERE current_group.id IS NULL)
 THEN RAISE EXCEPTION 'Native identity or group footprint requires explicit reconciliation'; END IF;
END $$;
UPDATE res_users u SET active=a.active,password=a.password""" + (",totp_secret=a.totp_secret,totp_last_counter=a.totp_last_counter" if schema['totp_secret'] else "") + """
 FROM restore_native_auth r,jsonb_to_recordset(r.payload->'users') AS a(id int,active boolean,password text,totp_secret text,totp_last_counter int)
 WHERE u.id=a.id;
DELETE FROM res_groups_users_rel;
INSERT INTO res_groups_users_rel(uid,gid)
 SELECT (u->>'id')::int,g::text::int FROM restore_native_auth r,jsonb_array_elements(r.payload->'users') u,jsonb_array_elements(u->'groups') g;
""" + ("""DELETE FROM auth_passkey_key;
INSERT INTO auth_passkey_key SELECT a.* FROM restore_native_auth r,jsonb_populate_recordset(NULL::auth_passkey_key,r.payload->'passkeys') a;
SELECT setval(pg_get_serial_sequence('auth_passkey_key','id'),COALESCE(max(id),1),count(*)>0) FROM auth_passkey_key;
""" if schema['passkeys'] else "") + ("DELETE FROM auth_totp_device;\n" if schema['totp_device'] else "")
