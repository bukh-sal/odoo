"""Resolve reviewed exact candidates without running source build backends.

Inputs and results are experimental until reviewed and copied to deploy locks.
No installed environment or running service is changed.
"""
import concurrent.futures,hashlib,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
PRIVATE=ROOT/'.local/g7-security-locks-01';assert not PRIVATE.exists();protect_directory(PRIVATE)
selection=json.loads((ROOT/'docs/evidence/G7/20261103-dependency-compatibility-01/candidate-selection.json').read_text())
normalize=lambda value:re.sub('[-_.]+','-',value).lower()
candidates={normalize(p['package']):p['version'] for p in selection['candidates']}
sources={'baseline':'deploy/requirements-py312.lock','r1':'deploy/requirements-r1.lock','build':'deploy/build-requirements.lock'}
pins={};before={}
for label,name in sources.items():
 raw=(ROOT/name).read_bytes();before[label]=dict(path=name,sha256=hashlib.sha256(raw).hexdigest())
 old={normalize(n):v for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s]+)',raw.decode(),re.M)}
 new={name:candidates.get(name,version) for name,version in old.items() if name!='pypdf2'}
 if 'pypdf2' in old:new['pypdf']=candidates['pypdf']
 if label=='build':new['packaging']='26.3' # wheel0.48 requires packaging>=24; already pinned in R1.
 pins[label]=dict(previous=old,target=new)
 with (OUT/(label+'.in')).open('x',encoding='utf8') as f:
  f.write('# Exact reviewed security maintenance; retain every unrelated qualified version.\n')
  f.write(''.join(name+'=='+version+'\n' for name,version in sorted(new.items())))
uv=Path(r'C:\Users\mesh\.local\bin\uv.exe');version=subprocess.check_output([str(uv),'--version'],text=True).strip();assert version.startswith('uv 0.13.5 ')
environment=os.environ.copy()
for name in list(environment):
 if name.startswith(('UV_INDEX','UV_EXTRA_INDEX','UV_DEFAULT_INDEX','UV_FIND_LINKS','UV_KEYRING','UV_INSECURE','PIP_INDEX','PIP_EXTRA_INDEX')):environment.pop(name)
def compile_one(label):
 args=[str(uv),'--no-config','pip','compile',str(OUT/(label+'.in')),'--generate-hashes','--python-platform','x86_64-manylinux_2_28','--python-version','3.12.16','--no-python-downloads','--no-build','--no-annotate','--no-header','--default-index','https://pypi.org/simple','--keyring-provider','disabled','--output-file',str(PRIVATE/(label+'.lock'))]
 result=subprocess.run(args,capture_output=True,env=environment,timeout=180)
 for suffix,data in [('stdout',result.stdout),('stderr',result.stderr)]:
  with (PRIVATE/(label+'.'+suffix)).open('xb') as f:f.write(data)
 record=dict(command=args,exit_code=result.returncode,no_build_backends=True,no_installed_environment_change=True)
 with (OUT/(label+'-compile01.json')).open('x',encoding='utf8') as f:json.dump(record,f,indent=2);f.write('\n')
 print(json.dumps(dict(label=label,exit_code=result.returncode,diagnostic=result.stderr.decode()[-1800:] if result.returncode else 'resolved')),flush=True)
 return record
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(compile_one,sources))
with (OUT/'input-review.json').open('x',encoding='utf8') as f:json.dump(dict(result='resolved' if all(r['exit_code']==0 for r in results) else 'requires_diagnosis',uv=version,before=before,pins=pins,no_canonical_locks_or_environment_changed=True),f,indent=2);f.write('\n')
raise SystemExit(any(r['exit_code'] for r in results))
