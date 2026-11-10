"""Private reference worker policy normalization for legacy operator configs.

The generic observer requires an explicit nine-field policy. Exact old reference
six-field configurations retain their original approved meaning without
rewriting the private file.
"""
import copy
from pathlib import Path
from modular_platform.operator_os import OperatorError

LEGACY_DESTINATION = 'http://document-stats:8080'
LEGACY_SERVICE = 'document-stats'
LEGACY_IMAGE_PREFIX = 'modular-document-stats@sha256:'
LEGACY_ENTRYPOINT = ['/venv/bin/python', '-m', 'services.document_stats.server']
LEGACY_COMMAND = ['--config', '/run/worker/config.json', '--host', '0.0.0.0', '--port', '8080']
LEGACY_ALIAS = 'document-stats'
SIX = {'project','service','network','public_config_volume','image','destination'}
NINE = SIX | {'entrypoint','command','network_alias'}


def normalize_reference_runtime(policy):
    """Return an exact nine-field policy for old exact reference configs only."""
    if not isinstance(policy, dict):
        raise OperatorError('Exact worker runtime policy required')
    if set(policy) == NINE:
        return copy.deepcopy(policy)
    if set(policy) != SIX:
        raise OperatorError('Exact worker runtime policy or supported legacy reference policy required')
    if (policy.get('destination') != LEGACY_DESTINATION or policy.get('service') != LEGACY_SERVICE
            or not isinstance(policy.get('image'), str) or not policy['image'].startswith(LEGACY_IMAGE_PREFIX)):
        raise OperatorError('Unknown legacy worker runtime shape; exact reference policy required')
    value = copy.deepcopy(policy)
    value.update(entrypoint=list(LEGACY_ENTRYPOINT), command=list(LEGACY_COMMAND), network_alias=LEGACY_ALIAS)
    return value


def runtime_policy_for(worker_path):
    from modular_platform.worker_operator import private_json
    return normalize_reference_runtime(private_json(worker_path)['runtime'])


def planning_reader(store,target_path,worker_path):
    from modular_platform.worker_operator import WorkerPlanningReader
    return WorkerPlanningReader(store,target_path,worker_path,runtime_policy=runtime_policy_for(worker_path))


def worker_operator(store,target_path,worker_path):
    from modular_platform.worker_operator import WorkerOperator
    return WorkerOperator(store,target_path,worker_path,runtime_policy=runtime_policy_for(worker_path))


def operator_observer(store,target_path):
    from modular_platform.worker_operator import operator_observer as generic
    path=Path(target_path).absolute().with_name('worker-target.json')
    policy=runtime_policy_for(path) if path.exists() else None
    return generic(store,target_path,runtime_policy=policy)
