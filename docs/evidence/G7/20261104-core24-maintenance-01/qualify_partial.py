"""Record real core24 result/UI residual and retire exact successful helpers."""
import base64,hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT));import maintain as m
from modular_platform.operator_os import protect_directory
from secret_scan import Scanner
state=m.load(m.PRIVATE/'state.json');assert state['phase']=='preserved_core24_needs_HTTP_UI09';native=m.context();assert native.config['generation']==5
run=ROOT/'.local/g7-ui-core24-01/smoke01';ui=m.load(run/'observations.json');process=m.load(run/'process.json');assert process['state']=='stopped' and process['exit']==dict(code=0,signal=None)
assert ui['Arabic']['lang']=='ar' and not ui['foreign_requests'] and not ui['runtime_exceptions'] and not ui['findings']
profile=m.load(ROOT/'.local/g7-ui-core24-01/browser-input.json')['profile'];command="$mpOwned='"+profile.replace("'","''")+"'; @(Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($mpOwned) } | Select-Object -ExpandProperty ProcessId) | ConvertTo-Json -Compress"
assert subprocess.check_output(['powershell','-NoProfile','-Command',command],stderr=subprocess.PIPE,timeout=30).strip() in (b'',b'[]',b'null')
after=m.snapshot('data-after-UI24',native);assert after==m.load(m.PRIVATE/'data-after.json');assert m.worker(native)==m.load(m.PRIVATE/'worker-before.json')
ids=subprocess.check_output(['docker','ps','-a','-q','--filter','label=com.modular.operation='+state['operation_id']],stderr=subprocess.PIPE,timeout=30).decode().split();assert len(ids)==7
old=m.load(m.PRIVATE/'target-before.json')['worker_id'];rows=json.loads(subprocess.check_output(['docker','inspect',*ids,old],stderr=subprocess.PIPE,timeout=30));retire=[];logs=protect_directory(m.PRIVATE/'retired-diagnostics')
suffixes={'checkpoint','native','metadata','assets','dispatch-fence','dispatch-reconcile','dispatch-enable'}
for row in rows:
 assert row['Id']!=native.config['worker_id'] and row['State']['Status']=='exited' and row['State']['ExitCode']==0
 if row['Id']==old:
  assert row['Image']==state['base_image'] and row['Config']['Labels']['com.docker.compose.project']==native.config['project']
 else:
  assert row['Config']['Labels']['com.modular.operation']==state['operation_id'] and row['Name'].startswith('/'+native.config['project']+'-op-'+state['operation_id']+'-')
  suffix=row['Name'].split(state['operation_id']+'-',1)[1];assert suffix in suffixes;suffixes.remove(suffix)
 mode=row['HostConfig']['LogConfig']['Type']
 if mode!='none':
  result=subprocess.run(['docker','logs',row['Id']],capture_output=True,timeout=30);assert result.returncode==0
  for ext,data in [('stdout',result.stdout),('stderr',result.stderr)]:
   with (logs/(row['Id']+'.'+ext)).open('xb') as f:f.write(data)
 retire.append(dict(id=row['Id'],name=row['Name'],image=row['Image'],exit_code=0,log_driver=mode))
assert not suffixes
values={k:base64.b64decode(v) for k,v in m.load(m.REFERENCE/'qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
# Deliberate complete table copies/checkpoints/configs are private recovery inputs,
# not clean logs. Never silently report those archives as a public diagnostic scan.
excluded={'data-before.stdout','data-after-review.stdout','data-after.stdout','data-before-UI24.stdout','data-after-UI24.stdout'}
streams=[p for folder in [m.PRIVATE,logs,run] for p in folder.iterdir() if p.is_file() and p.name not in excluded and p.suffix in ('.stdout','.stderr','.log')]
public=[p for p in OUT.iterdir() if p.is_file()]+[run/'observations.json',run/'network.json']+list(run.glob('*.png'))
assert not [f for p in streams+public for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))]
destination=OUT/'installed-smoke';destination.mkdir()
for name in ['observations.json','network.json','light-settings.png','dark-settings.png','light-labels.png','dark-labels.png','light-confirm.png','dark-confirm.png','Arabic-settings.png']:shutil.copyfile(run/name,destination/name)
receipt=dict(result='qualified_core24_native_preservation_and_partial_UI_with_residual_defect',utc=datetime.now(timezone.utc).isoformat(),image=state['image_id'],inventory=state['inventory_digest'],generation=5,operation_id=state['operation_id'],native_maintenance_completed=True,all17tables_preserved_except_predeclared_job_fences=True,all17tables_exact_after_readonly_UI=True,independent_worker_exact=True,owned_browser_exit0_no_profile_process=True,privacy=dict(known_values=len(values),actual_command_streams=len(streams),public_and_smoke_files=len(public),findings=0),remaining_defects=['Visual review: dark native close glyph remains indistinct because the white-close filter also inverts the generic filled button background. Keep native close appearance outside the generic button fill; no behavior rewrite.'],remaining_qualification=['Full installed UI09 contrast/focus/RTL/reflow/zoom/locale reconciliation, including waiting for workspace settings loading to finish before asserting translated administration labels.','Current final-image no-cache reproduction, provenance/privacy/kit/fresh developer path and final G7 audit.'],limits=['Smoke found no protocol/exceptions/missing image URL; visual review caught the residual, so UI09 remains FAILED.','Arabic HTML language updates immediately; this smoke screenshot captured loading, not a complete administration-locale walkthrough.','Old14de UI/performance/security proofs retain only their exact unchanged source scopes. Current selected567d has not yet passed independent reproduction; BOOT02 must be invalidated until qualified final-image reproduction.','Complete table stdout/snapshots and native/config/database/filestore checkpoint archives remain protected intentional inputs, excluded from clean command-log scope.'],intentional_private_table_stream_sha256={name:hashlib.sha256((m.PRIVATE/name).read_bytes()).hexdigest() for name in excluded if (m.PRIVATE/name).exists()},evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in public})
m.create(OUT/'partial-qualification.json',receipt)
for row in retire:
 current=json.loads(subprocess.check_output(['docker','inspect',row['id']],stderr=subprocess.PIPE,timeout=30))[0];assert current['State']['Status']=='exited' and current['State']['ExitCode']==0
 assert subprocess.check_output(['docker','rm',row['id']],stderr=subprocess.PIPE,timeout=30).decode().strip()==row['id']
m.create(OUT/'helper-retirement.json',dict(result='retired_eight_exact_successful_helpers_and_replaced_app',containers=retire,images_volumes_networks_databases_removed=0,private_checkpoint_and_diagnostics_retained=True))
m.phase(state,'core24_preserved_smoke_residual_close_defect_needs_full_UI09');print(json.dumps(dict(result=receipt['result'],helpers_retired=8,privacy_findings=0,UI09='failed',BOOT02='invalidated_current_image')))
