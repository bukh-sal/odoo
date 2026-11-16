"""Current integration authority over an existing checkpoint grant footprint.

Private recovery proof only; no new grants, application policy, or executable SQL
is accepted from a package or client.
"""
import copy
import re
from uuid import UUID

from .operator_os import OperatorError
from .plans import data_digest
from .resource_authority_recovery import resource_proof, verify_resource_proof

POLICY = 'r1-current-integration-grants-v1'
PROOF_NAME = 'integration-grants.json'
KEY = ('installation_id', 'plugin_id', 'workspace_id', 'capability')
FIELDS = set(KEY) | {'state', 'policy_version'}


def canonical_grants(rows):
    if not isinstance(rows, list):
        raise OperatorError('Explicit integration grant observation required')
    result = []; seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise OperatorError('Exact integration grant fields required')
        try:
            for field in ('installation_id', 'workspace_id'):
                if not isinstance(row[field], str) or str(UUID(row[field])) != row[field]:
                    raise ValueError()
            if (not isinstance(row['plugin_id'], str) or len(row['plugin_id']) > 180
                    or not re.fullmatch(r'[a-z][a-z0-9]*(\.[a-z][a-z0-9_]*){2,}', row['plugin_id'])
                    or not isinstance(row['capability'], str) or len(row['capability']) > 240
                    or not re.fullmatch(r'[a-z][a-z0-9_.]+:[a-z][a-z0-9_.]+', row['capability'])
                    or row['state'] not in ('approved', 'revoked')
                    or type(row['policy_version']) is not int or row['policy_version'] < 1):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise OperatorError('Malformed integration grant authority') from None
        key = tuple(row[field] for field in KEY)
        if key in seen:
            raise OperatorError('Duplicate integration grant authority')
        seen.add(key); result.append(copy.deepcopy(row))
    return sorted(result, key=lambda row: tuple(row[field] for field in KEY))


def restored_grants(checkpoint, current):
    current = {tuple(row[field] for field in KEY): row for row in canonical_grants(current)}
    result = canonical_grants(checkpoint)
    for row in result:
        match = current.get(tuple(row[field] for field in KEY))
        row['state'] = match['state'] if match else 'revoked'
        if match:
            row['policy_version'] = match['policy_version']
    return result


def grant_proof(decision, checkpoint, *, resource_checkpoint=None):
    checkpoint = canonical_grants(checkpoint)
    source = canonical_grants(decision['authority']['integration_grants'])
    expected = restored_grants(checkpoint, source)
    value = dict(schema_version=1, policy=POLICY, operation_id=decision['operation_id'],
                plan_hash=decision['plan_hash'], coordinated_checkpoint_digest=decision['checkpoint_digest'],
                source_authority_digest=data_digest(decision['authority']), checkpoint_grants=checkpoint,
                checkpoint_digest=data_digest(checkpoint), source_digest=data_digest(source),
                expected_grants=expected, expected_digest=data_digest(expected))
    if 'resource_access' in decision['authority']:
        value['resource_access'] = resource_proof(decision, resource_checkpoint)
    elif resource_checkpoint is not None:
        raise OperatorError('Checkpoint resources require current resource authority')
    return value


def verify_proof(value, decision):
    fields = {
            'schema_version', 'policy', 'operation_id', 'plan_hash', 'checkpoint_grants',
            'checkpoint_digest', 'source_digest', 'expected_grants', 'expected_digest',
            'coordinated_checkpoint_digest', 'source_authority_digest'}
    if 'resource_access' in decision['authority']:
        fields.add('resource_access')
    if not isinstance(value, dict) or set(value) != fields:
        raise OperatorError('Exact integration grant reconciliation proof required; keep traffic closed')
    canonical_grants(value['expected_grants'])
    resource_checkpoint = None
    if 'resource_access' in fields:
        resource_checkpoint = verify_resource_proof(value['resource_access'], decision)['checkpoint']
    if type(value['schema_version']) is not int or value != grant_proof(decision, value['checkpoint_grants'], resource_checkpoint=resource_checkpoint):
        raise OperatorError('Integration grant reconciliation proof differs from reviewed authority')
    return value


def reconciled_authority(decision, proof):
    expected = copy.deepcopy(decision['authority'])
    expected['integration_grants'] = verify_proof(proof, decision)['expected_grants']
    if 'resource_access' in proof:
        resources = proof['resource_access']['expected']
        if resources is None:
            expected.pop('resource_access', None)
        else:
            expected['resource_access'] = copy.deepcopy(resources)
    return expected


def proof_binding(proof):
    value = dict(integration_grants_policy=POLICY, integration_grants_proof_digest=data_digest(proof),
                integration_grants_digest=proof['expected_digest'])
    if 'resource_access' in proof:
        value['resource_authority_policy'] = proof['resource_access']['policy']
        value['resource_authority_digest'] = proof['resource_access']['expected_digest']
    return value
