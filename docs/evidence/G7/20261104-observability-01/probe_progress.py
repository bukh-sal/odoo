"""Actual owned subprocess observation/kill probe; never a lifecycle replay."""
import hashlib,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-observability-02'
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from modular_platform.operator_os import protect_directory
from modular_platform.operator_store import OperatorStore
from operation_progress import observe_execution,read_observation
class Store:
 _regular=staticmethod(OperatorStore._regular)
 def __init__(self,root,operation):self.root=root;self.operation=operation
 def bundle(self,operation):
  if operation!=self.operation:raise ValueError('unknown synthetic observation')
  return dict(plan_hash='sha256:'+'a'*64)
if len(sys.argv)>1:
 store=Store(Path(sys.argv[2]),sys.argv[3])
 with observe_execution(store,store.operation,'apply'):
  if sys.argv[1]=='hold':time.sleep(90)
  elif sys.argv[1]=='raise':raise RuntimeError('controlled observation exception')
 sys.exit(0)
assert not PRIVATE.exists();protect_directory(PRIVATE);OUT.mkdir(exist_ok=True)
store=Store(protect_directory(PRIVATE/'synthetic-control'),str(uuid4()));operation=store.operation
def write(name,value):
 with (OUT/name).open('x',encoding='utf8') as f:json.dump(value,f,indent=2);f.write('\n')
children=[]
def child(label,mode):
 out=(PRIVATE/(label+'.stdout')).open('xb');err=(PRIVATE/(label+'.stderr')).open('xb')
 # Windows venv python.exe is a launcher with a distinct child PID. Use its
 # exact selected base interpreter and selected environment's package path.
 code='import sys,runpy;sys.path.insert(0,'+repr(str(Path(sys.prefix)/'Lib/site-packages'))+');sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name="__main__")'
 process=subprocess.Popen([sys._base_executable,'-X','utf8','-c',code,str(Path(__file__).resolve()),mode,str(store.root),operation],stdout=out,stderr=err);out.close();err.close();children.append(process);return process
try:
 first=child('hold','hold');deadline=time.monotonic()+15
 while read_observation(store,operation)['state']=='not_recorded':
  assert first.poll() is None and time.monotonic()<deadline;time.sleep(.1)
 initial=read_observation(store,operation);assert initial['state']=='observing' and initial['process_id']==first.pid
 second=child('concurrent','return');assert second.wait(timeout=15)!=0
 assert b'LockBusy' in (PRIVATE/'concurrent.stderr').read_bytes()
 current=read_observation(store,operation);assert current['invocation_id']==initial['invocation_id']
 deadline=time.monotonic()+12
 while current['observed_at']==initial['observed_at']:
  assert time.monotonic()<deadline and first.poll() is None;time.sleep(.1);current=read_observation(store,operation)
 heartbeat_advance=current['elapsed_seconds']-initial['elapsed_seconds'];assert 4<=heartbeat_advance<=10
 killed_at=time.monotonic();first.kill();first.wait(timeout=10)
 killed=read_observation(store,operation);assert killed['observation_state']=='observing'
 deadline=time.monotonic()+25
 while read_observation(store,operation)['state']!='stale':
  assert time.monotonic()<deadline;time.sleep(.2)
 detection=time.monotonic()-killed_at;stale=read_observation(store,operation);assert detection<25 and stale['observation_state']=='observing'
 returned=child('return','return');assert returned.wait(timeout=15)==0;assert read_observation(store,operation)['state']=='returned'
 interrupted=child('exception','raise');assert interrupted.wait(timeout=15)!=0;assert read_observation(store,operation)['state']=='interrupted'
 # Actual new CLI readback against a completed current reference operation.
 reference=ROOT/'.local/release-kit-rehearsal/private/reference/operator';real=OperatorStore(reference/'control')
 import sqlite3
 with sqlite3.connect('file:'+real.database.as_posix()+'?mode=ro',uri=True) as database:
  row=database.execute("SELECT operation_id FROM operations WHERE state='completed' ORDER BY rowid DESC LIMIT 1").fetchone()
 assert row;before=real.status(row[0]);assert not (real.root/'progress').exists()
 command=[sys.executable,'-X','utf8',str(ROOT/'tools/modular.py'),'--config',str(reference/'trust.json'),'operations','--store',str(real.root),'show',row[0]]
 completed=subprocess.run(command,capture_output=True,timeout=30)
 (PRIVATE/'actual-current-show.stdout').write_bytes(completed.stdout);(PRIVATE/'actual-current-show.stderr').write_bytes(completed.stderr)
 assert completed.returncode==0, 'Current CLI show failed; inspect private diagnostics'
 shown=json.loads(completed.stdout);assert shown.pop('executor_observation')==dict(state='not_recorded',stale_after_seconds=20);assert shown==before==real.status(row[0]);assert not (real.root/'progress').exists()
 tests=[]
 for pattern in ['test_operation_progress.py','test_metadata_executor.py','test_executor_crash_fence.py']:
  result=subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',pattern,'-v'],capture_output=True,timeout=60)
  (PRIVATE/(pattern+'.stdout')).write_bytes(result.stdout);(PRIVATE/(pattern+'.stderr')).write_bytes(result.stderr);assert result.returncode==0,pattern
  tests.append(dict(pattern=pattern,exit_code=0,stream_sha256=hashlib.sha256(result.stdout+result.stderr).hexdigest()))
 result=dict(result='passed_actual_independent_operator_observation',utc=datetime.now(timezone.utc).isoformat(),heartbeat_advance_seconds=heartbeat_advance,forced_process_exit_code=first.returncode,stale_detected_after_kill_seconds=round(detection,3),stale_after_seconds=20,concurrent_process_refused=True,return_vs_exception_distinguished=True,all_owned_processes_exited=True,current_completed_journal_exact_readonly_legacy_not_recorded=True,current_operation_id=row[0],unit_suites=tests,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/operation_progress.py','tools/modular.py','tests/test_operation_progress.py','tests/test_metadata_executor.py']},limits=['Real subprocesses and OS locks/private files with synthetic observation metadata, not a native deployment execution.','Current completed real CLI journal read only; no lifecycle replay, approval change, Docker asset, database write or app image change.','Heartbeat means observer thread ran; stale is not proof of executor/child failure, rollback or safe retry.','Direct SDK callers are not wrapped; supported operator CLI apply/restore/resume are wrapped. Public HTTP DTO unchanged. Final operator kit source update pending.'])
 write('progress-qualification.json',result);print(json.dumps(dict(result=result['result'],heartbeat_advance_seconds=heartbeat_advance,stale_detection_seconds=round(detection,3),unit_suites=len(tests))))
finally:
 for process in children:
  if process.poll() is None:process.kill();process.wait(timeout=10)
