"""Approved metadata lifecycle using the existing coordinated executor loop.

This adapter controls host maintenance only. The independently configured remote
reference process is observed, never launched/stopped/updated by this executor.
"""
import hashlib,json
from pathlib import Path
from .native_executor import NativeExecutor
from .operator_os import OperatorError
from .plans import data_digest
from .reference_dispatch import ReferenceDispatchMaintenance,read_metadata,reference_observer


class ReferenceMetadataExecutor(NativeExecutor):
    def _observer_for(self,configuration):
        return reference_observer(self,configuration)

    def _dispatch(self):
        return ReferenceDispatchMaintenance(self)

    def _check_operation(self,bundle):
        plan=bundle['plan']
        if (not plan['artifacts'] or any(a['runtime']!='external_service' for a in plan['artifacts'])
                or 'staged_image' in bundle['operation_lock'] or plan['operation_type'] not in {'install','upgrade','enable','suspend','unregister'}
                or not plan['backup']['required'] or len(plan['site_ids'])!=1):
            raise OperatorError('Exact checkpointed single-site metadata-only lifecycle required')

    def _runtime_preflight(self,bundle):
        if bundle['operation_lock']['release']['core_inventory_digest']!=self.config['published_release']['core_inventory_digest']:
            raise OperatorError('Metadata lifecycle cannot change native image contents')
        runtime=self.observer.read()['runtime'];files=runtime['inventory']['files']
        names=['metadata_executor','external_metadata','external_planning','native_executor','dispatch_lifecycle',
            'dispatch_operator','dispatch_maintenance','reference_dispatch','operator_store','projection','planning_cli','plans']
        if runtime.get('published_release_protocol')!=1 or any(
                files.get('packages/platform_sdk/modular_platform/'+name+'.py')!=hashlib.sha256(Path(__file__).with_name(name+'.py').read_bytes()).hexdigest()
                for name in names):
            raise OperatorError('Metadata lifecycle requires an independently staged immutable image with current publication/dispatch readers')

    def _native_flags(self,bundle,plugins):
        self._check_operation(bundle)
        return None

    def _native_skip_reason(self,bundle):
        return 'Reviewed metadata publication only; no native addon/schema or remote runtime control'

    def _publish_metadata(self,bundle,payload,directory,image):
        from .contracts import load_json
        previous=load_json((self.store.root/'checkpoints'/bundle['plan']['operation_id']/'manifest.json').read_bytes())['previous_release']
        metadata=read_metadata(self,self.config)
        data=dict(bundle=bundle,base_state=previous,metadata_digest=data_digest(metadata),plugins=payload['plugins'],
            site_id=self.config['sites'][0]['site_id'],deployment_id=self.config['deployment_id'],database=self.config['sites'][0]['database'],
            inventory_digest=bundle['operation_lock']['release']['core_inventory_digest'])
        arguments,child=self._child(bundle['plan']['operation_id'],'metadata',image_id=image);arguments.insert(2,'-i')
        self._private_command(arguments+['-m','modular_platform.external_metadata'],directory/'metadata.log',input=json.dumps(data).encode())
        expected=dict(metadata_published=True,operation_id=bundle['plan']['operation_id'],native_maintenance=False,runtime_control=False)
        try:result=load_json((directory/'metadata.log').read_bytes())
        except (OSError,ValueError):raise OperatorError('Metadata child result is missing; reconcile actual state') from None
        if result!=expected:raise OperatorError('Metadata child result differs from exact operation; reconcile actual state')

