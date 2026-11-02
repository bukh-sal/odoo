"""Apply only reviewed exact lock solutions; no installed environment edit."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-security-locks-01'
review=json.loads((OUT/'input-review.json').read_text());solved=json.loads((OUT/'static-resolution.json').read_text())
assert solved['result']=='passed_static_complete_solutions'
changes=[]
for label,before in review['before'].items():
 path=ROOT/before['path'];old=path.read_bytes();assert hashlib.sha256(old).hexdigest()==before['sha256']
 new=(PRIVATE/(label+'-static.lock')).read_bytes();report=next(r for r in solved['solutions'] if r['label']==label)
 assert hashlib.sha256(new).hexdigest()==report['lock_sha256']
 (PRIVATE/(label+'-previous.lock')).write_bytes(old);path.write_bytes(new)
 changes.append(dict(path=before['path'],previous_sha256=before['sha256'],target_sha256=report['lock_sha256'],packages=report['packages']))
baseline=ROOT/'deploy/requirements-py312.in';assert not baseline.exists();baseline.write_bytes((OUT/'baseline.in').read_bytes())
(ROOT/'deploy/build-requirements.in').write_bytes((OUT/'build.in').read_bytes())
worker_dir=PRIVATE/'worker-derived'
args=[sys.executable,'-X','utf8','services/document_stats/lock_dependencies.py','--metadata',str(ROOT/'.local/g7-dependency-compatibility-01/final-installed-metadata.stdout'),'--output',str(worker_dir)]
r=subprocess.run(args,capture_output=True,timeout=90)
(PRIVATE/'worker-derive.stdout').write_bytes(r.stdout);(PRIVATE/'worker-derive.stderr').write_bytes(r.stderr);assert r.returncode==0,'Inspect derivation; main locks already applied, do not replay'
worker_pins=dict(re.findall(r'^([A-Za-z0-9_.-]+)==([^\s]+)',(worker_dir/'requirements.lock').read_text(),re.M))
assert len(worker_pins)==13 and worker_pins['pip']=='26.3' and worker_pins['cryptography']=='50.0.2'
for filename in ['requirements.lock','dependency-provenance.json']:
 path=ROOT/'services/document_stats'/filename;old=path.read_bytes();new=(worker_dir/filename).read_bytes()
 (PRIVATE/('worker-previous-'+filename)).write_bytes(old);path.write_bytes(new)
 changes.append(dict(path=path.relative_to(ROOT).as_posix(),previous_sha256=hashlib.sha256(old).hexdigest(),target_sha256=hashlib.sha256(new).hexdigest()))
path=ROOT/'deploy/runtime.lock.json';runtime=json.loads(path.read_text());old=path.read_bytes();(PRIVATE/'runtime-previous.json').write_bytes(old)
runtime['resolver']='Qualified modular_platform.resolution / resolvelib1.2.1, complete static observed Python3.12.16 target metadata; no source build hooks in planning'
runtime['dependency_review']=dict(adr='docs/architecture-decisions/0046-reviewed-python-security-maintenance.md',evidence='docs/evidence/G7/20261103-security-locks-01/static-resolution.json',baseline_packages=65,r1_packages=73,build_packages=4,worker_packages=13,qualification='candidate; actual images/native lifecycle/security/fresh release required')
path.write_text(json.dumps(runtime,indent=2)+'\n',encoding='utf8');changes.append(dict(path='deploy/runtime.lock.json',previous_sha256=hashlib.sha256(old).hexdigest(),target_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
report=dict(result='reviewed_exact_candidate_locks_applied_not_deployed',changes=changes,worker_derivation_command=args,worker_packages=worker_pins,no_installed_environment_or_running_service_change=True,limits=['Affected runtime acceptance needs target image qualification; historical installed evidence retained.','Frozen host tooling/global Python unchanged; app/worker images separately built and approved.'])
with (OUT/'applied-locks.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],files=len(changes),worker_packages=len(worker_pins))))
