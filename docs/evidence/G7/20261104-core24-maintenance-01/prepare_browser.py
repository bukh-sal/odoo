"""New current input/snapshot record; reuse the existing owned profile only."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT));import maintain as m
from modular_platform.operator_os import protect_directory,verify_private_directory
PRIVATE=ROOT/'.local/g7-ui-core24-01';assert not PRIVATE.exists();protect_directory(PRIVATE);protect_directory(PRIVATE/'smoke01')
state=m.load(m.PRIVATE/'state.json');assert state['phase']=='preserved_core24_needs_HTTP_UI09';native=m.context();assert native.config['generation']==5 and native.config['image_id']==state['image_id']
data=m.snapshot('data-before-UI24',native);assert data==m.load(m.PRIVATE/'data-after.json');m.create(PRIVATE/'tables-before.json',data)
record=m.load(ROOT/'.local/g7-ui-qualification-01/browser-input.json');assert record['image_id']==state['base_image'];record.update(image_id=state['image_id'],inventory_digest=state['inventory_digest'],generation=5,expected_board_name=data['mp_example_canvas_board'][0]['name']);verify_private_directory(record['profile']);m.create(PRIVATE/'browser-input.json',record)
worker=m.worker(native);rows=json.loads(subprocess.check_output(['docker','inspect',native.config['worker_id'],native.config['project']+'-db-1',native.config['project']+'-edge-1',worker['id']],stderr=subprocess.PIPE,timeout=30));assert all(r['State']['Running'] for r in rows) and rows[0]['Image']==record['image_id'];m.create(PRIVATE/'runtimes-before.json',rows)
m.create(OUT/'browser-prepared.json',dict(result='prepared_current_core24_snapshot_reusing_same_owned_profile',image=record['image_id'],inventory=record['inventory_digest'],generation=5,new_profiles=0,new_Docker_assets=0,all17tables_exact_to_verified_native_result=True))
print(json.dumps(dict(result='current_core24_browser_input_prepared',generation=5,image=record['image_id'],new_profile=False)))
