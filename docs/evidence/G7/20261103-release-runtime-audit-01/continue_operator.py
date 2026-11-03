"""Bounded continuation: stale fixture data and explicit subprocess SDK path."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent
rows=[]
for name in ['external_planning','workers','worker_authority']:
 env=dict(os.environ,PYTHONPATH=str(ROOT/'packages/platform_sdk')+os.pathsep+str(ROOT))
 r=subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_'+name+'.py','-v'],env=env,capture_output=True,text=True,encoding='utf8',timeout=120)
 row=dict(name=name,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr);rows.append(row)
 print(name,r.returncode,flush=True)
with (OUT/'operator-continuation.json').open('x',encoding='utf8') as f:json.dump(dict(result='passed' if all(r['exit_code']==0 for r in rows) else 'failed',utc=datetime.now(timezone.utc).isoformat(),source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['tests/test_external_planning.py','tests/test_workers.py']},reason='Metadata fixture selected same current version instead of upgrade; minimal recovery fixture omitted required release timestamp; authority subprocess requires SDK PYTHONPATH. Production checks/fixtures schemas/negative assertions unchanged.',records=rows),f,indent=2)
raise SystemExit(any(r['exit_code'] for r in rows))
