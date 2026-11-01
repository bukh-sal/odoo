"""Native availability changes through the existing full lifecycle executor."""
import hashlib,json
from pathlib import Path
from .native_executor import NativeExecutor
from .contracts import load_json
from .operator_os import OperatorError
from .plans import data_digest
from .reference_dispatch import read_metadata


class NativeFeatureExecutor(NativeExecutor):
    def _check_operation(self,bundle):
        plan=bundle['plan'];lock=bundle['operation_lock']
        if (plan['operation_type'] not in {'suspend','enable'} or not plan['backup']['required']
                or len(plan['site_ids'])!=1 or not plan['artifacts'] or any(a['runtime']!='native' for a in plan['artifacts'])
                or any(t['action']!=plan['operation_type'] for t in lock['targets'])
                or {'staged_image','platform_source_diff','native_core_changes','feature_states'}.intersection(lock)):
            raise OperatorError('Exact checkpointed single-site native feature operation required')

    def _runtime_preflight(self,bundle):
        if bundle['operation_lock']['release']!=self.config['published_release']:
            raise OperatorError('Feature lifecycle cannot change the published release')
        runtime=self.observer.read()['runtime'];files=runtime['inventory']['files']
        names=['native_feature_executor','coordinated_feature_metadata','feature_metadata','native_executor','operator_store',
            'lifecycle_planning','dispatch_lifecycle','dispatch_operator','dispatch_maintenance','plans']
        if runtime.get('published_release_protocol')!=1 or any(files.get('packages/platform_sdk/modular_platform/'+n+'.py')!=
                hashlib.sha256(Path(__file__).with_name(n+'.py').read_bytes()).hexdigest() for n in names):
            raise OperatorError('Coordinated feature lifecycle requires a compatible independently staged image')

    def _native_flags(self,bundle,plugins):
        self._check_operation(bundle);return None

    def _native_skip_reason(self,bundle):return 'Reviewed native feature availability only; no native install/unload or migration'

    def _publish_metadata(self,bundle,payload,directory,image):
        previous=load_json((self.store.root/'checkpoints'/bundle['plan']['operation_id']/'manifest.json').read_bytes())['previous_release']
        data=dict(bundle=bundle,base_state=previous,metadata_digest=data_digest(read_metadata(self,self.config)),
            site_id=self.config['sites'][0]['site_id'],deployment_id=self.config['deployment_id'],
            database=self.config['sites'][0]['database'],inventory_digest=bundle['operation_lock']['release']['core_inventory_digest'])
        args,_=self._child(bundle['plan']['operation_id'],'feature',image_id=image);args.insert(2,'-i')
        self._private_command(args+['-m','modular_platform.coordinated_feature_metadata'],directory/'feature.log',input=json.dumps(data).encode())
        expected=dict(feature_metadata_published=True,operation_id=bundle['plan']['operation_id'],native_maintenance=False,runtime_control=False)
        try:result=load_json((directory/'feature.log').read_bytes())
        except (OSError,ValueError):raise OperatorError('Feature result missing; reconcile actual state') from None
        if result!=expected:raise OperatorError('Feature result differs from exact operation; reconcile actual state')
