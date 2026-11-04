"""Read-only corrected operator preview; no registration, approval or mutation."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-uninstall-dispatch-01'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261103-fresh-target21-01')]
from lifecycle import f, context, snapshot, worker
from modular_platform.catalog import Catalog
from modular_platform.dispatch_lifecycle import SCHEMA
from modular_platform.uninstall_planning import prepare_current_image_uninstall

f.OUTPUT=OUT
state,native=context('connector')
assert native.config['generation']==5
before=snapshot(state,'uninstall-corrected-before');identity=worker(native,'uninstall-corrected-worker-before')
catalog=Catalog(native.catalog_root,native.validator,readonly=True)
observation=native.observer.read();document=native.observer.state(observation,catalog.snapshot())
original=subprocess.run
def capture(args,*a,**kw):
    result=original(args,*a,**kw)
    if isinstance(args,list) and 'mp.disposable=native-impact-inspection' in args:
        (PRIVATE/'corrected-impact-child.stdout').write_bytes(result.stdout)
        (PRIVATE/'corrected-impact-child.stderr').write_bytes(result.stderr)
    return result
with patch.object(subprocess,'run',side_effect=capture):
    impact=native.observer.native_impact(observation,catalog,site_id=state['site_id'],requested=['mp_example_notes_labels'])
assert impact['dispatch']==dict(state='present_requires_fence',tables=sorted(SCHEMA))
assert {p['plugin_id'] for p in impact['plugins']}=={'org.example.notes_labels'}
targets=[dict(installation_id=p['installation_id'],site_id=impact['site_id'],workspace_id=w,
    plugin_id=p['plugin_id'],action='uninstall') for p in impact['plugins'] for w in p['workspace_ids']]
assert len(targets)==2
bundle=prepare_current_image_uninstall(document,observation['sites'],catalog.snapshot(),impact=impact,targets=targets,
    operation_id=str(uuid4()),created_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
assert bundle['plan']['destructive'] and bundle['plan']['backup']['required']
assert snapshot(state,'uninstall-corrected-after')==before and worker(native,'uninstall-corrected-worker-after')==identity
f.guard(state)
result=dict(result='corrected_readonly_operator_preview_and_unregistered_proposal_passed',
    image_id=state['image_id'],configuration_generation=5,impact=impact,targets=targets,
    all17tables_worker_original_configs_exact=True,registered=False,approved=False,mutation_started=False,
    limits=['Host source preview only; installed application/core23 rollout and actual uninstall/recovery remain required.'])
with (OUT/'corrected-readonly.json').open('x',encoding='utf8') as stream:
    json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],scopes=len(targets),tables_preserved=True)))
