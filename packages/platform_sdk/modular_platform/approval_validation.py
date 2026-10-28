"""Independent validation for the initial native feature-control CLI path.

Code-changing plans require the separately staged release adapter in E-01d.
Until then they fail closed; a proposal cannot select its own runtime/config.
"""
from __future__ import annotations

import copy

from .catalog import Catalog
from .deployment import DockerObserver
from .operator_os import OperatorError
from .planning_cli import prepare_document
from .plans import check_bundle, data_digest


class IndependentValidator:
    def __init__(self, deployment_config, catalog_root, artifact_validator):
        self.observer = DockerObserver(deployment_config)
        self.catalog = Catalog(catalog_root, artifact_validator, readonly=True)

    def __call__(self, bundle):
        snapshot = self.catalog.snapshot()
        document = self.observer.state(self.observer.read(), snapshot)
        state = document['state']
        check_bundle(bundle, state)
        plan = bundle['plan']
        if plan['operation_type'] not in ('suspend', 'enable') or bundle['operation_lock']['release'] != state['release_lock']:
            raise OperatorError('Code-changing lifecycle plans require independently staged release validation (E-01d)')
        if plan['permission_changes'] or plan['trust_changes'] or plan['backup']['policy_id'] != 'development_checkpoint':
            raise OperatorError('This feature-control profile does not accept unrelated grant/trust/backup policy changes')
        document['request'] = {'operation_type': plan['operation_type'], 'requested': {},
            'targets': copy.deepcopy(bundle['operation_lock']['targets']),
            'operation_id': plan['operation_id'], 'created_at': plan['created_at'],
            'bindings': copy.deepcopy(state['bindings']), 'endpoints': copy.deepcopy(state['endpoints'])}
        recomputed = prepare_document(document, snapshot)
        if data_digest(recomputed) != data_digest(bundle):
            raise OperatorError('Independent reconstruction differs from the proposed exact plan')
        return state
