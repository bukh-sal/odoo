"""Fixed generic resource authority, reconciled before restored registry startup.

Public identities only. No application imports, table names, or executable policy
fragments are accepted from an application or recovery document.
"""
import copy
import json
import re
from uuid import UUID

from .operator_os import OperatorError
from .plans import data_digest

POLICY = 'r1-current-resource-authority-v1'
KEY = ('installation_id', 'plugin_id', 'workspace_id', 'model_name', 'resource_id')
POLICY_FIELDS = set(KEY) | {'policy_id', 'owner_id', 'state', 'revision', 'member_capabilities'}
GRANT_FIELDS = {'policy_id', 'principal_id', 'capability', 'state'}
FIRST_VERSION = (19, 0, 0, 2, 57)

SCHEMA_SELECT = """SELECT jsonb_build_object(
 'policy',to_regclass('public.mp_resource_policy') IS NOT NULL,
 'grant',to_regclass('public.mp_resource_grant') IS NOT NULL,
 'core_version',(SELECT latest_version FROM ir_module_module WHERE name='mp_core' AND state='installed'))"""


def _reject(message='Malformed resource authority; keep traffic closed'):
    raise OperatorError(message)


def _uuid(value):
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, AttributeError):
        return False


def _capability(value):
    return (isinstance(value, str) and len(value) <= 240
            and re.fullmatch(r'[a-z][a-z0-9_.]*', value) is not None)


def canonical_snapshot(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'policies', 'grants'}:
        _reject()
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        _reject()
    if not isinstance(value['policies'], list) or not isinstance(value['grants'], list):
        _reject()
    result = copy.deepcopy(value)
    policies = {}; identities = set(); grants = set()
    for row in result['policies']:
        if not isinstance(row, dict) or set(row) != POLICY_FIELDS:
            _reject()
        if (not all(_uuid(row[k]) for k in ('policy_id', 'installation_id', 'workspace_id', 'resource_id', 'owner_id'))
                or not isinstance(row['plugin_id'], str) or len(row['plugin_id']) > 180
                or re.fullmatch(r'[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*){2,}', row['plugin_id']) is None
                or not isinstance(row['model_name'], str) or len(row['model_name']) > 180
                or re.fullmatch(r'[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+', row['model_name']) is None
                or row['state'] not in ('active', 'revoked')
                or type(row['revision']) is not int or not 0 < row['revision'] < 2**31
                or not isinstance(row['member_capabilities'], list)
                or not all(_capability(c) for c in row['member_capabilities'])
                or len(set(row['member_capabilities'])) != len(row['member_capabilities'])):
            _reject()
        identity = tuple(row[k] for k in KEY)
        if row['policy_id'] in policies or identity in identities:
            _reject('Duplicate resource identity; keep traffic closed')
        policies[row['policy_id']] = row; identities.add(identity)
        row['member_capabilities'].sort()
    for row in result['grants']:
        if (not isinstance(row, dict) or set(row) != GRANT_FIELDS
                or not _uuid(row['policy_id']) or row['policy_id'] not in policies
                or not _uuid(row['principal_id']) or not _capability(row['capability'])
                or row['state'] not in ('approved', 'revoked')):
            _reject()
        key = (row['policy_id'], row['principal_id'], row['capability'])
        if key in grants:
            _reject('Duplicate resource grant; keep traffic closed')
        grants.add(key)
    result['policies'].sort(key=lambda row: row['policy_id'])
    result['grants'].sort(key=lambda row: (row['policy_id'], row['principal_id'], row['capability']))
    return result


def canonical_observation(value):
    """Only an observed pre-feature core can have a wholly absent schema."""
    if not isinstance(value, dict) or set(value) != {'schema', 'policies', 'grants'}:
        _reject('Explicit resource schema observation required')
    schema = value['schema']
    if (not isinstance(schema, dict) or set(schema) != {'policy', 'grant', 'core_version'}
            or type(schema['policy']) is not bool or type(schema['grant']) is not bool
            or not isinstance(schema['core_version'], str)
            or re.fullmatch(r'[0-9]+(\.[0-9]+){4}', schema['core_version']) is None):
        _reject('Unsupported resource schema observation')
    version = tuple(int(part) for part in schema['core_version'].split('.'))
    if schema['policy'] != schema['grant']:
        _reject('Partial resource authority schema; keep traffic closed')
    if not schema['policy']:
        if version >= FIRST_VERSION or value['policies'] != [] or value['grants'] != []:
            _reject('Resource authority missing from a feature-capable core')
        return None
    if version < FIRST_VERSION:
        _reject('Resource authority schema does not match core identity')
    return canonical_snapshot(dict(schema_version=1, policies=value['policies'], grants=value['grants']))


def authority_select(base, *, present):
    """Fixed alternative chosen by psql before absent relations are parsed."""
    policies = "'[]'::jsonb"; grants = "'[]'::jsonb"
    if present:
        policies = """COALESCE((SELECT jsonb_agg(jsonb_build_object(
         'policy_id',r.public_id,'installation_id',i.public_id,'plugin_id',i.plugin_id,
         'workspace_id',w.public_id,'model_name',r.model_name,'resource_id',r.resource_id,
         'owner_id',p.public_id,'state',r.state,'revision',r.revision,
         'member_capabilities',r.member_capabilities)) FROM mp_resource_policy r
         JOIN mp_plugin_installation i ON i.id=r.installation_id
         JOIN mp_workspace w ON w.id=r.workspace_id JOIN mp_principal p ON p.id=r.owner_id),'[]'::jsonb)"""
        grants = """COALESCE((SELECT jsonb_agg(jsonb_build_object(
         'policy_id',r.public_id,'principal_id',p.public_id,'capability',g.capability,'state',g.state))
         FROM mp_resource_grant g JOIN mp_resource_policy r ON r.id=g.policy_id
         JOIN mp_principal p ON p.id=g.principal_id),'[]'::jsonb)"""
    return ('SELECT (' + base.strip().removesuffix(';') + ") || jsonb_build_object('resource_access',"
            "jsonb_build_object('schema',(" + SCHEMA_SELECT + "),'policies'," + policies
            + ",'grants'," + grants + '));')


def reconcile(checkpoint, current):
    """Retain content footprint, apply current policy, never resurrect a share."""
    checkpoint = canonical_snapshot(checkpoint); current = canonical_snapshot(current)
    policies = {row['policy_id']: row for row in current['policies']}
    same_keys = {tuple(row[k] for k in KEY): row['policy_id'] for row in current['policies']}
    result = copy.deepcopy(checkpoint); retained = set()
    for row in result['policies']:
        ident = row['policy_id']; retained.add(ident)
        match = policies.get(ident)
        if match:
            if (any(row[k] != match[k] for k in (*KEY, 'owner_id'))
                    or match['revision'] < row['revision']
                    or match['revision'] == row['revision'] and match != row):
                _reject('Resource identity or monotonic revision changed')
            if match['revision'] == row['revision']:
                old = [g for g in checkpoint['grants'] if g['policy_id'] == ident]
                new = [g for g in current['grants'] if g['policy_id'] == ident]
                if old != new:
                    _reject('Resource grants changed without a policy revision')
            row.update(copy.deepcopy(match))
        else:
            if tuple(row[k] for k in KEY) in same_keys or row['revision'] == 2**31-1:
                _reject('Resource identity was replaced or revision exhausted')
            row.update(state='revoked', member_capabilities=[], revision=row['revision'] + 1)
    # Keep checkpoint tombstones and new current grants for retained resources.
    indexed = {(g['policy_id'], g['principal_id'], g['capability']): dict(g, state='revoked')
               for g in checkpoint['grants']}
    for grant in current['grants']:
        if grant['policy_id'] in retained:
            indexed[(grant['policy_id'], grant['principal_id'], grant['capability'])] = copy.deepcopy(grant)
    result['grants'] = list(indexed.values())
    return canonical_snapshot(result)


def resource_proof(decision, checkpoint):
    source = canonical_snapshot(decision['authority']['resource_access'])
    checkpoint = canonical_snapshot(checkpoint) if checkpoint is not None else None
    expected = reconcile(checkpoint, source) if checkpoint is not None else None
    return dict(policy=POLICY, source_digest=data_digest(source), checkpoint=checkpoint,
                checkpoint_digest=data_digest(checkpoint), expected=expected, expected_digest=data_digest(expected))


def verify_resource_proof(value, decision):
    if (not isinstance(value, dict) or set(value) != {'policy', 'source_digest', 'checkpoint',
            'checkpoint_digest', 'expected', 'expected_digest'}
            or value != resource_proof(decision, value['checkpoint'])):
        _reject('Resource reconciliation proof differs from current reviewed authority')
    return value


def overlay_sql(snapshot):
    """Apply an already reconciled snapshot; FKs/row-count proof fail closed.

    No business records or principals are created. New current grants can target
    only an existing checkpoint policy and principal. Final observation proves
    exact equality before any registry startup or traffic resume.
    """
    snapshot = canonical_snapshot(snapshot)
    payload = json.dumps(snapshot).replace("'", "''")
    return ("CREATE TEMP TABLE restore_resources(payload jsonb); INSERT INTO restore_resources VALUES ('"
            + payload + "'::jsonb);\n" + """
UPDATE mp_resource_policy SET state='revoked',member_capabilities='[]'::jsonb;
UPDATE mp_resource_grant SET state='revoked';
UPDATE mp_resource_policy r SET state=a.state,revision=a.revision,member_capabilities=a.member_capabilities
 FROM restore_resources s,jsonb_to_recordset(s.payload->'policies') AS a(
 policy_id text,installation_id text,plugin_id text,workspace_id text,model_name text,
 resource_id text,owner_id text,state text,revision integer,member_capabilities jsonb),
 mp_plugin_installation i,mp_workspace w,mp_principal p
 WHERE r.public_id=a.policy_id AND r.installation_id=i.id AND i.public_id=a.installation_id
 AND i.plugin_id=a.plugin_id AND r.workspace_id=w.id AND w.public_id=a.workspace_id
 AND r.model_name=a.model_name AND r.resource_id=a.resource_id AND r.owner_id=p.id AND p.public_id=a.owner_id;
INSERT INTO mp_resource_grant(policy_id,principal_id,capability,state,create_uid,write_uid,create_date,write_date)
 SELECT r.id,p.id,a.capability,a.state,1,1,timezone('UTC',now()),timezone('UTC',now())
 FROM restore_resources s,jsonb_to_recordset(s.payload->'grants') AS a(
 policy_id text,principal_id text,capability text,state text),mp_resource_policy r,mp_principal p
 WHERE r.public_id=a.policy_id AND p.public_id=a.principal_id
 ON CONFLICT(policy_id,principal_id,capability) DO UPDATE SET state=EXCLUDED.state;
""")
