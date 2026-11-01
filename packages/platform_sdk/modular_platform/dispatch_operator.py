"""Host-only adapter to existing private executor child/capture facilities.

Not wired into apply/recovery until release reconciliation and resume are ready.
No public CLI or application-side approval path is introduced by this helper.
"""
import hashlib
import json
from pathlib import Path
from uuid import UUID
from .contracts import load_json
from .operator_os import OperatorError,protect_directory
from .operator_store import _write_new


class DispatchMaintenance:
    def __init__(self,native):
        self.native=native
        if len(native.config['sites'])!=1:raise OperatorError('Dispatch profile requires one exact configured site')

    def run(self,action,operation,directory,*,database=None,release_digest):
        if action not in {'observe','fence'} or str(UUID(operation))!=operation:
            raise OperatorError('Exact dispatch maintenance action/operation required')
        site=self.native.config['sites'][0]
        if database is not None and database!=site['database']:
            raise OperatorError('Dispatch child must use the exact current configuration; use a verified replacement adapter for restore')
        directory=protect_directory(Path(directory));record=directory/(action+'.json')
        if record.exists():raise OperatorError('Dispatch child already attempted; inspect retained result and actual state before continuation')
        helper=Path(__file__).with_name('dispatch_lifecycle.py').read_text(encoding='utf8')
        script=Path(__file__).with_name('dispatch_maintenance.py').read_text(encoding='utf8')
        source='LIFECYCLE_SOURCE='+repr(helper)+'\n'+script
        binding=dict(action=action,database=site['database'],site_id=site['site_id'],release_digest=release_digest,operation_id=operation)
        _write_new(directory/(action+'-request.json'),dict(**binding,helper_sha256=hashlib.sha256(helper.encode()).hexdigest(),script_sha256=hashlib.sha256(script.encode()).hexdigest(),image_id=self.native.config['image_id']))
        args,child=self.native._child(operation,'dispatch-'+action)
        args.insert(2,'-i')
        self.native._private_command(args+['-c',source],directory/(action+'.stdout'),input=json.dumps(binding).encode(),timeout=45)
        value=load_json((directory/(action+'.stdout')).read_bytes())
        if not isinstance(value,dict) or set(value)!={'action','result'} or value['action']!=action:
            raise OperatorError('Exact dispatch child result missing; inspect private diagnostics')
        result=value['result']
        if action=='fence' and result is not None and (result.get('operation_id')!=operation or not result.get('requires_reviewed_resume')):
            raise OperatorError('Dispatch fence result differs from this operation')
        _write_new(record,dict(child=child,**value))
        return result
