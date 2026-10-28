"""Independent reconstruction of native feature/current-image install plans.

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
from .lifecycle_planning import validate_install_targets


class IndependentValidator:
    def __init__(self, deployment_config, catalog_root, artifact_validator, *, quiesced=False):
        self.observer = DockerObserver(deployment_config)
        self.catalog = Catalog(catalog_root, artifact_validator, readonly=True)
        self.quiesced = quiesced

    def __call__(self, bundle):
        snapshot = self.catalog.snapshot()
        observation = self.observer.read(quiesced=True) if getattr(self, 'quiesced', False) else self.observer.read()
        document = self.observer.state(observation, snapshot)
        state = document['state']
        check_bundle(bundle, state)
        plan = bundle['plan']
        if plan['operation_type'] == 'install':
            validate_install_targets(document, observation['sites'], bundle['operation_lock']['targets'])
            expected = copy.deepcopy(state['release_lock'])
            expected.update(generation=expected['generation'] + 1, created_at=plan['created_at'])
            proposed = copy.deepcopy(bundle['operation_lock']['release'])
            # New concrete scopes are reconstructed below from independently
            # checked targets; they do not authorize different executable bytes.
            proposed.pop('service_selection')
            expected.pop('service_selection')
            if proposed != expected:
                raise OperatorError('New executable bytes require an independently staged release image')
        elif plan['operation_type'] not in ('suspend', 'enable') or bundle['operation_lock']['release'] != state['release_lock']:
            raise OperatorError('This lifecycle operation requires the staged release adapter')
        if plan['permission_changes'] or plan['trust_changes'] or plan['backup']['policy_id'] != 'development_checkpoint':
            raise OperatorError('This profile does not accept unrelated grant/trust/backup policy changes')
        document['request'] = {'operation_type': plan['operation_type'], 'requested': {},
            'targets': copy.deepcopy(bundle['operation_lock']['targets']),
            'operation_id': plan['operation_id'], 'created_at': plan['created_at'],
            'endpoints': copy.deepcopy(state['endpoints'])}
        if plan['operation_type'] != 'install':
            document['request']['bindings'] = copy.deepcopy(state['bindings'])
        recomputed = prepare_document(document, snapshot)
        if data_digest(recomputed) != data_digest(bundle):
            raise OperatorError('Independent reconstruction differs from the proposed exact plan')
        return state
