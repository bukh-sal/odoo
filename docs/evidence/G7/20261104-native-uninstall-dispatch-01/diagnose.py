"""Preserve exact read-only child diagnostics without changing impact behavior."""
import json,subprocess,sys,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-uninstall-dispatch-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f,context,snapshot,worker
from modular_platform.catalog import Catalog
from modular_platform.resolution import PlanningError
f.OUTPUT=OUT;state,native=context('connector');assert PRIVATE.is_dir()
before=snapshot(state,'uninstall-impact-diagnostic-before');identity=worker(native,'uninstall-impact-diagnostic-worker-before')
catalog=Catalog(native.catalog_root,native.validator,readonly=True);observation=native.observer.read();original=subprocess.run;captured=[]
def run(args,*a,**kw):
 result=original(args,*a,**kw)
 if isinstance(args,list) and 'mp.disposable=native-impact-inspection' in args:
  assert len(captured)==0
  (PRIVATE/'impact-child.stdout').write_bytes(result.stdout);(PRIVATE/'impact-child.stderr').write_bytes(result.stderr)
  captured.append(dict(exit_code=result.returncode,stderr_sha256=hashlib.sha256(result.stderr).hexdigest()))
 return result
with patch.object(subprocess,'run',side_effect=run):
 try:native.observer.native_impact(observation,catalog,site_id=state['site_id'],requested=['mp_example_notes_labels'])
 except PlanningError as error:reason=str(error)
 else:raise AssertionError('Prior failed read-only impact unexpectedly succeeded')
assert len(captured)==1 and captured[0]['exit_code']!=0
assert snapshot(state,'uninstall-impact-diagnostic-after')==before and worker(native,'uninstall-impact-diagnostic-worker-after')==identity;f.guard(state)
(PRIVATE/'data-before.json').write_text(json.dumps(before,indent=2)+'\n')
with (OUT/'read-only-refusal.json').open('x',encoding='utf8') as stream:json.dump(dict(result='current_native_uninstall_impact_refused_readonly',image_id=state['image_id'],configuration_generation=5,public_error=reason,child=captured[0],all17tables_worker_exact=True,plan_approval_mutation_created=False),stream,indent=2);stream.write('\n')
print(json.dumps(dict(result='read_only_diagnostic_captured',exit_code=captured[0]['exit_code'],all17tables_worker_exact=True)))
