"""Exact approved feature metadata changes without migration/restart claims."""
import json
import hashlib
from pathlib import Path

from .catalog import Catalog
from .operator_os import OperatorError, OperationLocks, protect_directory
from .operator_store import _write_new


class FeatureExecutor:
    def __init__(self,native):
        self.native=native;self.store=native.store;self.observer=native.observer

    def apply(self,operation):
        bundle=self.store.bundle(operation);plan=bundle['plan']
        if plan['operation_type'] not in ('suspend','enable'):
            raise OperatorError('Feature executor requires suspension or enablement')
        with OperationLocks(self.store.root/'locks',plan['deployment_id'],plan['site_ids']) as locks:
            if self.store.status(operation)['state']=='completed':
                self.native.mirror_progress(operation)
                return self.store.status(operation)
            if plan['backup']['required']:
                raise OperatorError('Checkpointed native features require the coordinated executor')
            from .dispatch_operator import DispatchMaintenance
            if DispatchMaintenance(self.native).present():
                raise OperatorError('Durable work requires a fresh checkpointed feature plan before reservation')
            if plan['permission_changes']:
                files=self.observer.read()['runtime']['inventory']['files']
                for name in ('feature_metadata.py','lifecycle_planning.py'):
                    if files.get('packages/platform_sdk/modular_platform/'+name)!=hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest():
                        raise OperatorError('Grant reapproval requires a compatible independently staged feature image')
            validate=self.native._validate()
            self.store.reserve(operation,locks,validate)
            self.native.mirror_progress(operation)
            directory=protect_directory(self.store.root/'stages')/operation
            failure='STAGING_FAILED'
            try:
                if directory.exists():raise OperatorError('Existing feature stage requires reconciliation')
                directory=protect_directory(directory);_write_new(directory/'bundle.json',bundle)
                self.native._topology()
                self.store.advance(operation,locks,'staged')
                self.native.mirror_progress(operation)
                state=validate(bundle)
                self.store.before_mutation(operation,locks,validate)
                failure='MUTATION_FAILED'
                args,name=self.native._child(operation,'feature');args.insert(2,'-i')
                payload={'site_id':self.native.config['sites'][0]['site_id'],'operation_id':operation,
                    'plan_hash':bundle['plan_hash'],'security_metadata_digest':state['security_metadata_digest'],
                    'targets':bundle['operation_lock']['targets']}
                if plan['permission_changes']:payload.update(permission_changes=plan['permission_changes'],policy_version=plan['policy_version'])
                self.native._private_command(args+['-c',Path(__file__).with_name('feature_metadata.py').read_text()],
                    directory/'feature.log',input=json.dumps(payload).encode())
                self.store.advance(operation,locks,'metadata_published')
                self.native.mirror_progress(operation)
                failure='READINESS_FAILED'
                catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
                observation=self.observer.read();state=self.observer.state(observation,catalog)['state']
                if state['release_digest']!=plan['target_release_digest'] or state['bindings']!=bundle['operation_lock']['bindings']:
                    raise OperatorError('Feature operation changed the executable release or bindings')
                for target in bundle['operation_lock']['targets']:
                    row=next(item for item in state['installations'] if item['installation_id']==target['installation_id'] and item['workspace_id']==target['workspace_id'])
                    expected='enabled' if target['action']=='enable' else 'suspended'
                    if row['state']!='installed' or row['feature_state']!=expected:
                        raise OperatorError('Feature metadata readiness differs from approved targets')
                for change in plan['permission_changes']:
                    target=next(t for t in bundle['operation_lock']['targets'] if t['plugin_id']==change['plugin_id'] and t['workspace_id']==change['workspace_id'])
                    grant=next((g for s in observation['sites'] for g in s['grants'] if s['site_id']==target['site_id']
                        and g['installation_id']==target['installation_id'] and g['workspace_id']==target['workspace_id'] and g['capability']==change['capability']),None)
                    if not grant or grant['state']!='approved' or grant['policy_version']!=plan['policy_version']:
                        raise OperatorError('Feature grant readiness differs from exact approved reapproval')
                self.store.advance(operation,locks,'ready')
                self.store.advance(operation,locks,'completed')
                self.native.mirror_progress(operation)
                return self.store.status(operation)
            except BaseException:
                self.store.fail(operation,locks,code=failure)
                raise
