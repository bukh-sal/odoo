"""Read-only native-current-image planning with a real external metadata root."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,PRIVATE,MARKER,context,f,base
state,native=context();cycle=f.load(MARKER);assert cycle['suspend']['state']=='preservation_verified'
before=base.snapshot(state,'manager02-current-cli-data-before');physical=base.worker(native,'manager02-current-cli-worker-before')
canvas=next(p for p in native.config['published_release']['plugins'] if p['plugin_id']=='org.example.canvas')
command=base.prefix()+['plugin','plan-current-install','--deployment-config',str(native.target_path),'--store',str(native.catalog_root),
    '--operator-store',str(native.store.root),'--site',cycle['scope']['site_id'],'--workspace',cycle['scope']['workspace_id'],
    '--plugin','org.example.canvas','--version',canvas['version'],'--digest',canvas['digest']]
bundle=json.loads(f.command('manager02-current-image-cli',command));f.save('current-image-cli-plan.json',bundle)
assert bundle['plan']['operation_type']=='install' and bundle['operation_lock']['targets']==[
    dict(installation_id=next(r['installation_id'] for r in f.load(OUT/'suspend-state-before.json')['installations'] if r['plugin_id']=='org.example.canvas'),
        site_id=cycle['scope']['site_id'],workspace_id=cycle['scope']['workspace_id'],plugin_id='org.example.canvas',action='install')]
old=[p for p in native.config['published_release']['plugins'] if p['runtime']=='external_service']
assert [p for p in bundle['operation_lock']['release']['plugins'] if p['runtime']=='external_service']==old
assert native._validate()(bundle)['release_lock']==native.config['published_release']
assert base.snapshot(state,'manager02-current-cli-data-after')==before
assert base.worker(native,'manager02-current-cli-worker-after')==physical
f.save('current-image-cli-qualification.json',dict(result='passed_actual_current_image_cli_with_independent_external_reader',
    read_only_plan=True,explicit_operator_store_separate_from_catalog=True,independent_reconstruction_passed=True,
    same_external_metadata_pins_retained=True,all17tables_and_external_worker_unchanged=True,
    no_registration_approval_apply_or_native_install=True,canvas_data_or_product_features_changed=False,
    purpose='Qualify the required current-image native CLI with an existing external metadata root; C Canvas was only nominated, never installed.'))
f.guard(state);print('Actual current-image CLI independently reconstructs a read-only native plan retaining external pins; no Canvas install/data change')
