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
from .lifecycle_planning import prepare_current_install_targets, install_activation_targets, prepare_current_feature


class IndependentValidator:
    def __init__(self, deployment_config, catalog_root, artifact_validator, *, quiesced=False, stage_store=None, external_reader=None):
        self.observer = DockerObserver(deployment_config,external_reader=external_reader)
        self.catalog = Catalog(catalog_root, artifact_validator, readonly=True)
        self.quiesced = quiesced
        self.stage_store=stage_store

    def __call__(self, bundle):
        snapshot = self.catalog.snapshot()
        observation = self.observer.read(quiesced=True) if getattr(self, 'quiesced', False) else self.observer.read()
        document = self.observer.state(observation, snapshot)
        state = document['state']
        check_bundle(bundle, state)
        plan = bundle['plan']
        if plan['trust_changes'] or plan['backup']['policy_id'] != 'development_checkpoint':
            raise OperatorError('This profile does not accept unrelated grant/trust/backup policy changes')
        if 'staged_image' in bundle['operation_lock']:
            if not getattr(self,'stage_store',None):
                raise OperatorError('Staged image requires independently owned release metadata')
            from .release_staging import prepare_staged_plan
            if plan['operation_type']=='remove':
                self.observer.removal_site_inventory(observation)
            descriptor,record=self.stage_store.load(bundle['operation_lock']['staged_image'])
            recomputed=prepare_staged_plan(document,observation['sites'],snapshot,record['runtime'],descriptor,
                targets=bundle['operation_lock']['targets'],operation_type=plan['operation_type'],
                operation_id=plan['operation_id'],created_at=plan['created_at'],base_runtime=observation.get('runtime'),
                feature_states=bundle['operation_lock'].get('feature_states',[]))
            if data_digest(recomputed)!=data_digest(bundle):
                raise OperatorError('Independently staged reconstruction differs from proposed exact plan')
            return state
        if plan['artifacts'] and all(r['runtime']=='external_service' for r in plan['artifacts']):
            from .external_planning import prepare_external_metadata,external_selections
            if self.observer.external_reader is None or 'external_state' not in observation:
                raise OperatorError('External metadata requires a fresh independently configured reader')
            recomputed=prepare_external_metadata(document,observation['sites'],snapshot,
                targets=bundle['operation_lock']['targets'],operation_type=plan['operation_type'],
                external_state=observation['external_state'],selections=external_selections(bundle),
                feature_states=bundle['operation_lock'].get('feature_states',[]),
                operation_id=plan['operation_id'],created_at=plan['created_at'])
            if data_digest(recomputed)!=data_digest(bundle):
                raise OperatorError('Independent external metadata reconstruction differs from proposed exact plan')
            return state
        if plan['permission_changes'] and plan['operation_type'] not in ('install', 'uninstall', 'enable'):
            raise OperatorError('Current-image feature/control profile does not accept unrelated grant changes')
        if plan['operation_type'] == 'uninstall':
            from .uninstall_planning import prepare_current_image_uninstall
            from .lifecycle_impact import impact_view
            bound = bundle['operation_lock'].get('native_uninstall_impact')
            if not isinstance(bound, dict) or not {'site_id', 'requested_addons'} <= bound.keys():
                raise OperatorError('Native uninstall requires a bound independently reconstructed impact')
            impact_view(bound, operation_id=plan['operation_id'], plan_hash=bundle['plan_hash'], observed_at=plan['created_at'])
            impact = self.observer.native_impact(observation, self.catalog, site_id=bound['site_id'], requested=bound['requested_addons'])
            recomputed = prepare_current_image_uninstall(document, observation['sites'], snapshot,
                impact=impact, targets=copy.deepcopy(bundle['operation_lock']['targets']),
                operation_id=plan['operation_id'], created_at=plan['created_at'])
            if data_digest(recomputed) != data_digest(bundle):
                raise OperatorError('Independent uninstall impact/epoch reconstruction differs from proposed exact plan')
            return state
        if plan['operation_type'] == 'install':
            expected = copy.deepcopy(state['release_lock'])
            expected.update(generation=expected['generation'] + 1, created_at=plan['created_at'])
            proposed = copy.deepcopy(bundle['operation_lock']['release'])
            # New concrete scopes are reconstructed below from independently
            # checked targets; they do not authorize different executable bytes.
            proposed.pop('service_selection')
            expected.pop('service_selection')
            if proposed != expected:
                raise OperatorError('New executable bytes require an independently staged release image')
            recomputed = prepare_current_install_targets(document, observation['sites'], snapshot,
                activation_targets=install_activation_targets(bundle), operation_id=plan['operation_id'], created_at=plan['created_at'])
            if data_digest(recomputed) != data_digest(bundle):
                raise OperatorError('Independent native install scopes/feature states/grants differ from proposed exact plan')
            return state
        elif plan['operation_type'] not in ('suspend', 'enable') or bundle['operation_lock']['release'] != state['release_lock']:
            raise OperatorError('This lifecycle operation requires the staged release adapter')
        recomputed = prepare_current_feature(document, observation['sites'], snapshot,
            targets=copy.deepcopy(bundle['operation_lock']['targets']), operation_type=plan['operation_type'],
            operation_id=plan['operation_id'], created_at=plan['created_at'])
        if data_digest(recomputed) != data_digest(bundle):
            raise OperatorError('Independent reconstruction differs from the proposed exact plan')
        return state
