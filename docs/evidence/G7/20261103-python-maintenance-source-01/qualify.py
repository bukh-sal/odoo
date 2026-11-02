"""Once-only affected source/contract consumer regression records."""
import concurrent.futures,hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
names=['contracts','artifacts','resolution','plans','planning_cli','client_release',
       'core_upgrade','core_python_maintenance','release_staging','platform_deploy',
       'approval_fences','operator_store','manager_planning','manager_contracts',
       'operation_contracts','lifecycle_planning','external_planning','platform_compatibility',
       'distribution_metadata','start_worker']
commands=[(name,[sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p','test_'+name+'.py','-v']) for name in names]
commands.append(('typescript',[r'C:\Program Files\nodejs\node.exe',r'C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js','--prefix','packages/host_sdk','run','check']))
def one(item):
 name,args=item;target=OUT/(name+'.json');assert not target.exists()
 result=subprocess.run(args,capture_output=True,text=True,encoding='utf8',timeout=240)
 counts=re.findall(r'Ran (\d+) tests? in',result.stderr)
 record=dict(command=args,exit_code=result.returncode,tests=int(counts[-1]) if counts else None,stdout=result.stdout,stderr=result.stderr)
 with target.open('x',encoding='utf8') as f:json.dump(record,f,indent=2);f.write('\n')
 print(json.dumps(dict(record=name,exit_code=result.returncode,tests=record['tests'])),flush=True)
 return dict(record=target.name,exit_code=result.returncode,tests=record['tests'])
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,commands))
if not any(r['exit_code'] for r in results):results.append(one(('freeze',[sys.executable,'-X','utf8','tools/check_contract_freeze.py'])))
source=['packages/platform_sdk/modular_platform/'+n+'.py' for n in ['release_staging','planning_cli','plans','projection']]
source.extend(['platform_addons/mp_core/__manifest__.py','tests/test_core_python_maintenance.py','docs/contracts/freeze-v1.json'])
record=dict(result='passed' if not any(r['exit_code'] for r in results) else 'failed',utc=datetime.now(timezone.utc).isoformat(),
 git_base=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 tracked_diff_sha256=hashlib.sha256(subprocess.check_output(['git','diff','--binary'])).hexdigest(),
 source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in source},records=results,
 limits=['Source/contract consumers only; no rebuilt dependency image, registry, actual lifecycle/recovery, full security or fresh release qualification.'])
with (OUT/'qualification.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2);f.write('\n')
raise SystemExit(any(r['exit_code'] for r in results))
