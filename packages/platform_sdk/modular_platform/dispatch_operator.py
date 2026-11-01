"""Host-only adapter to existing private executor child/capture facilities.

Used by the existing approved executor and private recovery reviews. No public
CLI or application-side approval path is introduced by this helper.
"""
import ast
import hashlib
import json
from pathlib import Path
from uuid import UUID,uuid4
from .contracts import load_json
from .operator_os import OperatorError,protect_directory
from .operator_store import _write_new
from .plans import data_digest
from .deployment import _run


class DispatchMaintenance:
    def __init__(self,native):
        self.native=native
        if len(native.config['sites'])!=1:raise OperatorError('Dispatch profile requires one exact configured site')

    def present(self,*,configuration=None):
        config=configuration or self.native.config;self._configuration(config)
        raw=_run(['docker','exec','-i',self.native.observer._container('db'),'psql','-X','-qAt','-U','postgres','-d',config['sites'][0]['database'],'-v','ON_ERROR_STOP=1'],
            input=b"SELECT jsonb_build_array(to_regclass('public.mp_job') IS NOT NULL,to_regclass('public.mp_outbox') IS NOT NULL,to_regclass('public.mp_dispatch_control') IS NOT NULL);")
        value=load_json(raw)
        if not isinstance(value,list) or len(value)!=3 or any(type(v)is not bool for v in value):raise OperatorError('Exact dispatch presence observation required')
        return any(value)

    @staticmethod
    def require_native(snapshot,*,closed=False):
        if (not isinstance(snapshot,dict) or snapshot.get('profile')!='r1-native-dispatch-v1'
                or any(snapshot.get(k)!=0 for k in ['external_installations','active_credentials','api_keys','uncertain_jobs'])
                or closed and (snapshot.get('control') is None and any(t['rows'] for t in snapshot.get('tables',{}).values())
                    or snapshot.get('control') is not None and snapshot['control']['state'] not in {'paused','restoring'})):
            raise OperatorError('Known reconciled native dispatch profile required; external or uncertain effects keep traffic fenced')
        return snapshot

    @staticmethod
    def require_runtime(runtime):
        required={'addons/mp_core/job_dispatch.py','packages/platform_sdk/modular_platform/job_runner.py','packages/platform_sdk/modular_platform/worker_start.py'}
        if not required<=set(runtime.get('inventory',{}).get('files',{})):
            raise OperatorError('Runtime lacks the scoped native job adapter; explicit queue reconciliation is required before lifecycle mutation')

    def run(self,action,operation,directory,*,database=None,release_digest,control_release=None,expected_digest=None,configuration=None,review_id=None):
        if action not in {'observe','fence','enable'} or str(UUID(operation))!=operation:
            raise OperatorError('Exact dispatch maintenance action/operation required')
        config=configuration or self.native.config;self._configuration(config);site=config['sites'][0]
        if database is not None and database!=site['database']:
            raise OperatorError('Dispatch child must use the exact current configuration; use a verified replacement adapter for restore')
        directory=protect_directory(Path(directory));record=directory/(action+'.json')
        if record.exists():raise OperatorError('Dispatch child already attempted; inspect retained result and actual state before continuation')
        helper=Path(__file__).with_name('dispatch_lifecycle.py').read_text(encoding='utf8')
        script=Path(__file__).with_name('dispatch_maintenance.py').read_text(encoding='utf8')
        source='LIFECYCLE_SOURCE='+repr(helper)+'\n'+script
        binding=dict(action=action,database=site['database'],site_id=site['site_id'],release_digest=release_digest,control_release=control_release,operation_id=operation,expected_digest=expected_digest)
        _write_new(directory/(action+'-request.json'),dict(**binding,helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),script_sha256=hashlib.sha256(script.encode()).hexdigest(),image_id=config['image_id']))
        args,child=self.native._child(operation,self._suffix(action,review_id),image_id=config['image_id'])
        args.insert(2,'-i')
        self.native._private_command(args+['-c',source],directory/(action+'.stdout'),input=json.dumps(binding).encode(),timeout=45)
        value=load_json((directory/(action+'.stdout')).read_bytes())
        if not isinstance(value,dict) or set(value)!={'action','result'} or value['action']!=action:
            raise OperatorError('Exact dispatch child result missing; inspect private diagnostics')
        result=value['result']
        if action=='fence' and result is not None and (result.get('operation_id')!=operation or not result.get('requires_reviewed_resume')):
            raise OperatorError('Dispatch fence result differs from this operation')
        if action=='enable' and (not isinstance(result,dict) or result.get('dispatch_enabled') is not True):
            raise OperatorError('Exact dispatch enable result missing; reconcile actual state before continuing')
        _write_new(record,dict(child=child,**value))
        return result

    def _configuration(self,config):
        if (len(config['sites'])!=1 or any(config[k]!=self.native.config[k] for k in ['project','deployment_id'])
                or config['sites'][0]['site_id']!=self.native.config['sites'][0]['site_id']):
            raise OperatorError('Exact same independent deployment/site configuration required')

    @staticmethod
    def _suffix(action,review_id):
        if review_id is not None and str(UUID(review_id))!=review_id:raise OperatorError('Exact review correlation required')
        return 'dispatch-'+action+('-'+review_id.replace('-','') if review_id else '')

    def inspect(self,*,configuration=None,release_digest=None,control_release=None):
        config=configuration or self.native.config;self._configuration(config);operation=str(uuid4())
        if not self.present(configuration=config):return None
        return self.run('observe',operation,self.native.store.root/'dispatch-inspections'/operation,
            configuration=config,release_digest=release_digest or data_digest(config['published_release']),control_release=control_release)

    def inspect_current(self,*,configuration=None):
        """Independent recovery observation, even after a partial publication.

        Observe actual DB/control tags, then bind them in the private review;
        this does not approve or enable anything described by the database.
        """
        config=configuration or self.native.config;self._configuration(config)
        if not self.present(configuration=config):return None
        database=config['sites'][0]['database']
        raw=_run(['docker','exec','-i',self.native.observer._container('db'),'psql','-X','-qAt','-U','postgres','-d',database,'-v','ON_ERROR_STOP=1'],
            input=b"SELECT jsonb_build_object('published',(SELECT value FROM ir_config_parameter WHERE key='mp.release_digest'),'control',(SELECT min(release_digest) FROM mp_dispatch_control));")
        tags=load_json(raw)
        return self.inspect(configuration=config,release_digest=tags['published'],control_release=tags['control'])

    def reconcile_jobs(self,operation,directory,*,previous_release,release_digest,inventory_digest,preview=False,configuration=None,review_id=None):
        """Host caller supplies an independently validated target configuration.

        Preview rolls back its private native transaction. Mutating use belongs
        inside the existing approved executor/review paths, which are not wired
        by this method alone. A DB/application flag never grants that approval.
        """
        config=configuration or self.native.config;self._configuration(config)
        if str(UUID(operation))!=operation:
            raise OperatorError('Job reconciliation requires the same independent deployment/site')
        action='preview' if preview else 'reconcile';directory=protect_directory(Path(directory));dest=directory/(action+'.json')
        if dest.exists():raise OperatorError('Job reconciliation already attempted; inspect exact private result before continuation')
        # Read only the host implementation, never a path/source supplied by an
        # artifact or application. Supports retained pre-adapter image restore.
        path=Path(__file__).resolve().parents[3]/'platform_addons/mp_core/job_dispatch.py'
        text=path.read_text(encoding='utf8');tree=ast.parse(text)
        functions=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='reconcile_release']
        if len(functions)!=1:raise OperatorError('Fixed host job reconciliation source missing')
        function=ast.get_source_segment(text,functions[0]);script=Path(__file__).with_name('dispatch_jobs_maintenance.py').read_text(encoding='utf8')
        body=dict(action=action,database=config['sites'][0]['database'],site_id=config['sites'][0]['site_id'],deployment_id=config['deployment_id'],
            previous_release=previous_release,release_digest=release_digest,inventory_digest=inventory_digest,operation_id=operation)
        _write_new(directory/(action+'-request.json'),dict(**body,function_sha256=hashlib.sha256(function.encode()).hexdigest(),script_sha256=hashlib.sha256(script.encode()).hexdigest(),image_id=config['image_id']))
        args,child=self.native._child(operation,self._suffix(action,review_id),image_id=config['image_id']);args.insert(2,'-i')
        self.native._private_command(args+['-c','RECONCILE_SOURCE='+repr(function)+'\n'+script],directory/(action+'.stdout'),input=json.dumps(body).encode(),timeout=120)
        value=load_json((directory/(action+'.stdout')).read_bytes())
        if (not isinstance(value,dict) or set(value)!={'action','mutation_committed','result'} or value['action']!=action
                or value['mutation_committed'] is not (not preview) or value['result'].get('target_release')!=release_digest
                or not value['result'].get('requires_independent_resume') or value['result'].get('dispatch_enabled') is not False):
            raise OperatorError('Exact paused reconciliation proof missing; traffic must remain closed')
        _write_new(dest,dict(child=child,**value));return value['result']
