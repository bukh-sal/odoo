"""Exact approved feature metadata changes without migration/restart claims."""
import json
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
                self.native._private_command(args+['-c',Path(__file__).with_name('feature_metadata.py').read_text()],
                    directory/'feature.log',input=json.dumps(payload).encode())
                self.store.advance(operation,locks,'metadata_published')
                self.native.mirror_progress(operation)
                failure='READINESS_FAILED'
                catalog=Catalog(self.native.catalog_root,self.native.validator,readonly=True).snapshot()
                state=self.observer.state(self.observer.read(),catalog)['state']
                if state['release_digest']!=plan['target_release_digest'] or state['bindings']!=bundle['operation_lock']['bindings']:
                    raise OperatorError('Feature operation changed the executable release or bindings')
                for target in bundle['operation_lock']['targets']:
                    row=next(item for item in state['installations'] if item['installation_id']==target['installation_id'] and item['workspace_id']==target['workspace_id'])
                    expected='enabled' if target['action']=='enable' else 'suspended'
                    if row['state']!='installed' or row['feature_state']!=expected:
                        raise OperatorError('Feature metadata readiness differs from approved targets')
                self.store.advance(operation,locks,'ready')
                self.store.advance(operation,locks,'completed')
                self.native.mirror_progress(operation)
                return self.store.status(operation)
            except BaseException:
                self.store.fail(operation,locks,code=failure)
                raise
