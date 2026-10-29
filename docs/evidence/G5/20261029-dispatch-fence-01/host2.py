"""Discriminate Windows test timeout with direct interpreter and live test logs."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from source import ROOT,OUTPUT,RUNNER,source
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_store import _write_new
assert not (OUTPUT/'source-host2.json').exists()
code='PATTERNS='+repr(['test_restore_dispatch.py','test_recovery.py','test_unchanged_recovery.py','test_operator_store.py'])+'\n'+RUNNER.replace('verbosity=1','verbosity=2')
command=[sys._base_executable,'-X','utf8','-c',code]
with (OUTPUT/'source-host2.stdout.log').open('xb') as stdout,(OUTPUT/'source-host2.stderr.log').open('xb') as stderr:
 p=subprocess.Popen(command,cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'.venv/Lib/site-packages')),stdout=stdout,stderr=stderr)
 _write_new(ROOT/'.local/g5-dispatch/source-host2.json',dict(state='running',pid=p.pid,direct_base_interpreter=True))
 try:exit_code=p.wait(timeout=600)
 except subprocess.TimeoutExpired:
  p.kill();p.wait(timeout=30);raise RuntimeError('Direct known test runner timed out; inspect last streamed case before any next action')
assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in source.items())
report=dict(result='passed' if exit_code==0 else 'failed',exit_code=exit_code,command=command,source_sha256=source)
if exit_code==0:report['summary']=json.loads((OUTPUT/'source-host2.stdout.log').read_text(encoding='utf8').splitlines()[-1])
(OUTPUT/'source-host2.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
(ROOT/'.local/g5-dispatch/source-host2.json').write_text(json.dumps(dict(state='terminal',pid=p.pid,exit_code=exit_code))+'\n',encoding='utf8')
print(json.dumps(dict(result=report['result'],summary=report.get('summary'))));raise SystemExit(exit_code)
