"""Host-only optional reference executor composition.

This module is never imported by the generic SDK/child. The explicit OS CLI
selects it from the protected deployment configuration and exact plan/profile.
"""
import hashlib
import json
from pathlib import Path

from modular_platform.contracts import load_json
from modular_platform.dispatch_operator import DispatchMaintenance
from modular_platform.metadata_sql import read_metadata
from modular_platform.native_executor import NativeExecutor, StagedNativeExecutor
from modular_platform.native_feature_executor import NativeFeatureExecutor
from modular_platform.restore_executor import RestoreExecutor
from modular_platform.unchanged_recovery import UnchangedReleaseRecovery
from modular_platform.operator_os import OperatorError
from modular_platform.plans import data_digest

from reference_operator.dispatch import ReferenceDispatchMaintenance, reference_observer
from reference_operator.recovery import ReferenceRecoveryDispatch, reference_needed
from reference_operator.worker import normalize_reference_runtime


def reference_present(configuration):
    return any(plugin.get('runtime') == 'external_service'
               for plugin in configuration.get('published_release', {}).get('plugins', []))


class ReferenceHooks:
    def _observer_for(self, configuration):
        return reference_observer(self, configuration)

    def _dispatch(self):
        from modular_platform.recurrence_maintenance import selected
        recurring = selected(self)
        if recurring is not None:
            if reference_present(self.config):
                raise OperatorError('Combined external and recurrence maintenance requires separate qualification')
            return recurring
        if reference_present(self.config):
            return ReferenceDispatchMaintenance(self)
        return DispatchMaintenance(self)

    def _metadata_script(self, script, source):
        if not reference_present(self.config):
            return source
        extension = (Path(__file__).with_name('lifecycle_reference.py')).read_text(encoding='utf8')
        return ("import modular_platform.dispatch_lifecycle as _dl\n"
                "exec(compile(" + repr(extension) + ",'reference_operator.lifecycle_reference','exec'),_dl.__dict__)\n" + source)

    def _checkpoint_scope_fields(self, manifest, snapshot):
        scope = super()._checkpoint_scope_fields(manifest, snapshot)
        if manifest.get('reference_policy') is not None:
            scope['reference'] = manifest['reference_policy']
        return scope

    def _checkpoint_profile_fields(self, previous, actual, helper):
        if actual.get('profile', '').startswith('r1-reference-'):
            previous['reference_policy'] = helper.policy_for(actual)
            previous['external_dispatch'] = ('Outbound stateless reference profile fenced; independent current publication is not rolled back.')
        else:
            super()._checkpoint_profile_fields(previous, actual, helper)


class ReferenceNativeExecutor(ReferenceHooks, NativeExecutor):
    pass


class ReferenceStagedNativeExecutor(ReferenceHooks, StagedNativeExecutor):
    pass


class ReferenceNativeFeatureExecutor(ReferenceHooks, NativeFeatureExecutor):
    pass


class ReferenceMetadataExecutor(ReferenceNativeExecutor):
    """External-only metadata lifecycle using the generic native executor loop."""
    def _check_operation(self, bundle):
        plan = bundle['plan']
        if (not plan['artifacts'] or any(a['runtime'] != 'external_service' for a in plan['artifacts'])
                or 'staged_image' in bundle['operation_lock'] or plan['operation_type'] not in {'install','upgrade','enable','suspend','unregister'}
                or not plan['backup']['required'] or len(plan['site_ids']) != 1):
            raise OperatorError('Exact checkpointed single-site metadata-only lifecycle required')
        self._reference_operation = plan['operation_id']

    def _runtime_preflight(self, bundle):
        if bundle['operation_lock']['release']['core_inventory_digest'] != self.config['published_release']['core_inventory_digest']:
            raise OperatorError('Metadata lifecycle cannot change native image contents')
        runtime = self.observer.read()['runtime']
        files = runtime['inventory']['files']
        root = Path(__file__).resolve().parents[2]
        generic = ['external_metadata','external_planning','native_executor','dispatch_lifecycle','dispatch_operator',
                   'dispatch_maintenance','operator_store','projection','planning_cli','plans']
        if runtime.get('published_release_protocol') != 1 or any(
                files.get('packages/platform_sdk/modular_platform/'+name+'.py') !=
                hashlib.sha256((root/'packages/platform_sdk/modular_platform'/(name+'.py')).read_bytes()).hexdigest()
                for name in generic):
            raise OperatorError('Metadata lifecycle requires the exact current generic image readers')
        review = load_json((Path(__file__).with_name('source-review.json')).read_bytes())
        optional = {'dispatch.py','recovery.py','transition.py','executor.py','worker.py','lifecycle_reference.py'}
        if set(review) != optional:
            raise OperatorError('Optional reference source review record is incomplete')
        for name, expected in review.items():
            path = Path(__file__).with_name(name)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise OperatorError('Optional reference operator source changed after review')

    def _dispatch(self):
        return ReferenceDispatchMaintenance(self, operation=getattr(self, '_reference_operation', None))

    def _native_flags(self, bundle, plugins):
        self._check_operation(bundle)
        return None

    def _native_skip_reason(self, bundle):
        return 'Reviewed metadata publication only; no native addon/schema or remote runtime control'

    def _publish_metadata(self, bundle, payload, directory, image):
        previous = load_json((self.store.root/'checkpoints'/bundle['plan']['operation_id']/'manifest.json').read_bytes())['previous_release']
        metadata = read_metadata(self, self.config)
        data = dict(bundle=bundle, base_state=previous, metadata_digest=data_digest(metadata),
                    plugins=payload['plugins'], site_id=self.config['sites'][0]['site_id'],
                    deployment_id=self.config['deployment_id'], database=self.config['sites'][0]['database'],
                    inventory_digest=bundle['operation_lock']['release']['core_inventory_digest'])
        arguments, child = self._child(bundle['plan']['operation_id'], 'metadata', image_id=image)
        arguments.insert(2, '-i')
        self._private_command(arguments+['-m','modular_platform.external_metadata'], directory/'metadata.log', input=json.dumps(data).encode())
        expected = dict(metadata_published=True, operation_id=bundle['plan']['operation_id'],
                        native_maintenance=False, runtime_control=False)
        try:
            result = load_json((directory/'metadata.log').read_bytes())
        except (OSError, ValueError):
            raise OperatorError('Metadata child result is missing; reconcile actual state') from None
        if result != expected:
            raise OperatorError('Metadata child result differs from exact operation; reconcile actual state')


class ReferenceRestoreExecutor(RestoreExecutor):
    def _reference_recovery_supported(self):
        return True

    def _supported_profiles(self):
        return super()._supported_profiles() | {'r1-reference-stateless-dispatch-v1'}

    def _restore_result_dispatch_fields(self, result, helper, dispatch_ready):
        if dispatch_ready['profile'] == 'r1-reference-stateless-dispatch-v1':
            result['reference_policy'] = helper.policy_for(dispatch_ready)
        else:
            super()._restore_result_dispatch_fields(result, helper, dispatch_ready)

    def _resume_dispatch_same(self, helper, current, previous, result):
        if previous['profile'] == 'r1-reference-stateless-dispatch-v1':
            return helper.same_restored_dispatch(current, previous, result.get('reference_policy'))
        return super()._resume_dispatch_same(helper, current, previous, result)

    def _resume_observation(self, result):
        if result.get('dispatch', {}).get('profile') == 'r1-reference-stateless-dispatch-v1':
            return self._recovery_observer(self.config).read()
        return super()._resume_observation(result)

    def _dispatch_helper(self, *, manifest=None, purpose='restored'):
        if getattr(self, '_operation', None) is None:
            if reference_present(self.config):
                raise OperatorError('Reference recovery requires an exact independent operation')
            return DispatchMaintenance(self.native)
        bundle = self.store.bundle(self._operation)
        if manifest is None:
            manifest = load_json((self.store.root/'checkpoints'/self._operation/'manifest.json').read_bytes())
        if reference_needed(self.native, bundle, manifest):
            return ReferenceRecoveryDispatch(self.native, bundle, manifest, purpose=purpose)
        return super()._dispatch_helper(manifest=manifest, purpose=purpose)

    def _recovery_observer(self, configuration, *, manifest=None, purpose='restored'):
        helper = self._dispatch_helper(manifest=manifest, purpose=purpose)
        return helper.observer(configuration) if isinstance(helper, ReferenceRecoveryDispatch) else super()._recovery_observer(configuration, manifest=manifest, purpose=purpose)

    def _continuation_class(self):
        from reference_operator.recovery import ReferenceRestoreContinuation
        return ReferenceRestoreContinuation


class ReferenceUnchangedRecovery(ReferenceHooks, UnchangedReleaseRecovery):
    def _dispatch(self):
        from modular_platform.recurrence_maintenance import selected
        recurring = selected(self.native)
        if recurring is not None:
            if reference_present(self.native.config):
                raise OperatorError('Combined external and recurrence maintenance requires separate qualification')
            return recurring
        if reference_present(self.native.config):
            return ReferenceDispatchMaintenance(self.native)
        return UnchangedReleaseRecovery._dispatch(self)


def native_executor_class(*, staged=False, metadata=False, feature=False):
    if staged:
        return ReferenceStagedNativeExecutor
    if feature:
        return ReferenceNativeFeatureExecutor
    if metadata:
        return ReferenceMetadataExecutor
    return ReferenceNativeExecutor


def executor_for_target(store, target_path, catalog, validator):
    config = load_json(Path(target_path).read_bytes())
    if reference_present(config):
        return ReferenceNativeExecutor(store, target_path, catalog, validator)
    return NativeExecutor(store, target_path, catalog, validator)


def executor_for(store, target_path, catalog, validator, bundle):
    metadata = bool(bundle['plan']['artifacts']) and all(
        artifact['runtime'] == 'external_service' for artifact in bundle['plan']['artifacts'])
    if metadata:
        return ReferenceMetadataExecutor(store, target_path, catalog, validator)
    config = load_json(Path(target_path).read_bytes())
    reference = reference_present(config)
    staged = 'staged_image' in bundle['operation_lock']
    feature = bundle['plan']['operation_type'] in ('suspend', 'enable') and bundle['plan']['backup']['required']
    if reference:
        cls = ReferenceStagedNativeExecutor if staged else ReferenceNativeFeatureExecutor if feature else ReferenceNativeExecutor
        return cls(store, target_path, catalog, validator)
    if staged:
        return StagedNativeExecutor(store, target_path, catalog, validator)
    if feature:
        return NativeFeatureExecutor(store, target_path, catalog, validator)
    return NativeExecutor(store, target_path, catalog, validator)


def wrap_feature_executor(native):
    from modular_platform.feature_executor import FeatureExecutor
    return FeatureExecutor(native)


def restore_executor_for(native):
    if reference_present(native.config):
        return ReferenceRestoreExecutor(native)
    return RestoreExecutor(native)


def unchanged_recovery_for(native):
    if reference_present(native.config):
        return ReferenceUnchangedRecovery(native)
    return UnchangedReleaseRecovery(native)
