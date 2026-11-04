"""Prepare a readonly UI audit and reversible zoom on the existing owned profile."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core24-ui-audit-01'
sys.path[:0]=[str(ROOT/'packages/platform_sdk'),str(ROOT/'tools'),str(ROOT/'docs/evidence/G7/20261104-core24-maintenance-01')]
from modular_platform.operator_os import protect_directory
import maintain as m
assert not PRIVATE.exists();protect_directory(PRIVATE)
for name in ['baseline','zoom200']:protect_directory(PRIVATE/name)
native=m.context();record=m.load(ROOT/'.local/g7-ui-core24-01/browser-input.json')
assert native.config['generation']==5 and native.config['image_id']==record['image_id']
profile=Path(record['profile']);prefs=profile/'Default/Preferences'
command="$mpOwned='"+str(profile).replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
assert subprocess.check_output(['powershell','-NoProfile','-Command',command],stderr=subprocess.PIPE,timeout=30).strip() in (b'',b'[]',b'null')
v=json.loads(prefs.read_bytes());partition=v.get('partition',{})
backup=dict(partition_existed='partition' in v,keys={key:dict(existed=key in partition,value=partition.get(key)) for key in ['default_zoom_level','per_host_zoom_levels']})
m.create(PRIVATE/'zoom-before.json',backup)
m.PRIVATE=PRIVATE
data=m.snapshot('data-before',native);assert data==m.load(ROOT/'.local/g7-ui-core24-01/tables-before.json')
m.create(PRIVATE/'tables-before.json',data);m.create(PRIVATE/'worker-before.json',m.worker(native))
rows=json.loads(subprocess.check_output(['docker','inspect',native.config['worker_id'],native.config['project']+'-db-1',native.config['project']+'-edge-1',m.worker(native)['id']],stderr=subprocess.PIPE,timeout=30))
stable=[dict(id=r['Id'],image=r['Image'],started=r['State']['StartedAt'],pid=r['State']['Pid'],mounts=r['Mounts'],networks=r['NetworkSettings']['Networks']) for r in rows]
m.create(PRIVATE/'runtimes-before.json',stable)
original=ROOT/'docs/evidence/G7/20261104-core24-maintenance-01/browser_runtime.mjs'
text=original.read_text();needle="await rpc('Emulation.setDeviceMetricsOverride',{width:1280,height:900,deviceScaleFactor:1,mobile:false});"
assert text.count(needle)==1;text=text.replace(needle,'')
assert text.count("'--headless=new'")==1;text=text.replace("'--headless=new'","'--headless=new','--window-size=1280,900'")
(OUT/'browser_runtime.mjs').write_text(text,encoding='utf8')
m.create(OUT/'preparation.json',dict(result='prepared_actual_core24_readonly_UI_audit_same_profile',image=record['image_id'],generation=5,
    original_runtime_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),changes=['Skip CDP device metrics override; use real1280x900 browser window.',
    'Only existing owned profile; reversible selected zoom preferences, original keys privately recorded.'],new_profiles=0,new_Docker_assets=0))
print(json.dumps(dict(result='prepared',generation=5,profile_processes=0,new_profiles=0)))
