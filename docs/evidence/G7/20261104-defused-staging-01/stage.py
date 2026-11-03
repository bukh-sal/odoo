"""Add one pure-wheel dependency with full exact static solution and unchanged pins."""
import email.parser,hashlib,json,re,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-defused-staging-01'
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import protect_directory
from modular_platform.resolution import resolve_release
from packaging.utils import canonicalize_name
assert not PRIVATE.exists();protect_directory(PRIVATE)
source=json.loads((ROOT/'.local/g7-native-libraries-01/defusedxml-source.json').read_text());wheel=ROOT/'.local/g7-native-libraries-01'/source['filename'];assert hashlib.sha256(wheel.read_bytes()).hexdigest()==source['sha256']
with zipfile.ZipFile(wheel) as z:
 metadata=email.parser.BytesParser().parsebytes(z.read('defusedxml-0.7.1.dist-info/METADATA'));tags=email.parser.BytesParser().parsebytes(z.read('defusedxml-0.7.1.dist-info/WHEEL')).get_all('Tag')
 notices={n:z.read(n) for n in z.namelist() if n.endswith(('LICENSE','LICENSE.txt','COPYING'))}
assert metadata['Name']=='defusedxml' and metadata['Version']=='0.7.1' and not metadata.get_all('Requires-Dist') and notices
candidate=dict(name='defusedxml',version='0.7.1',kind='wheel',digest='sha256:'+source['sha256'],requires_python=metadata.get('Requires-Python',''),requires_dist=[],tags=tags)
runtime=json.loads((ROOT/'.local/g7-release-runtime-audit-01/runtime-observation.json').read_text());assert runtime['python']=='3.12.16'
environment=dict(platform_version='0.1.22',native_runtime='odoo-19',markers=runtime['markers'],accepted_wheel_tags=runtime['accepted_wheel_tags'],core_addons=[])
observed=runtime['python_metadata'];assert not any(canonicalize_name(p['name'])=='defusedxml' for p in observed)
reports=[];changes=[]
for label,path in [('baseline','deploy/requirements-py312.lock'),('r1','deploy/requirements-r1.lock')]:
 file=ROOT/path;old=file.read_bytes();pins=dict(re.findall(r'^([A-Za-z0-9_.-]+)==([^\s]+)',old.decode(),re.M));target=dict(pins,defusedxml='0.7.1')
 solved=resolve_release([],observed+[candidate],environment,{},core_python=[n+'=='+v for n,v in target.items()]);actual={canonicalize_name(p['name']):p['version'] for p in solved['python']};assert actual=={canonicalize_name(n):v for n,v in target.items()}
 newline=b'\r\n' if b'\r\n' in old else b'\n';block=('defusedxml==0.7.1 \\'+newline.decode()+'    --hash=sha256:'+source['sha256']+newline.decode()).encode();new=old+(b'' if old.endswith(b'\n') else newline)+block
 (PRIVATE/(label+'-previous.lock')).write_bytes(old);(PRIVATE/(label+'-candidate.lock')).write_bytes(new)
 reports.append(dict(label=label,previous_packages=len(pins),target_packages=len(actual),previous_sha256=hashlib.sha256(old).hexdigest(),candidate_sha256=hashlib.sha256(new).hexdigest(),all_previous_bytes_preserved=True,added_only=dict(defusedxml='0.7.1'),solution=solved))
 changes.append((file,new))
# All review/solve checks finish before applying any canonical input.
for file,new in changes:file.write_bytes(new)
p=ROOT/'deploy/requirements-py312.in';old=p.read_bytes();assert b'defusedxml' not in old;(PRIVATE/'baseline-previous.in').write_bytes(old);p.write_bytes(old+b'\n# Required native spreadsheet XML entity protection (ADR0050).\ndefusedxml==0.7.1\n')
p=ROOT/'packages/platform_sdk/modular_platform/projection.py';old=p.read_bytes();assert old.count(b"PLATFORM_VERSION='0.1.21'")==1;p.write_bytes(old.replace(b"PLATFORM_VERSION='0.1.21'",b"PLATFORM_VERSION='0.1.22'"))
p=ROOT/'platform_addons/mp_core/__manifest__.py';old=p.read_bytes();assert old.count(b'19.0.0.1.21')==1;p.write_bytes(old.replace(b'19.0.0.1.21',b'19.0.0.1.22'))
for name,data in notices.items():
 dest=ROOT/'third_party/python/defusedxml-0.7.1'/Path(name).name;dest.parent.mkdir(exist_ok=True);assert not dest.exists();dest.write_bytes(data)
record=dict(result='complete_static_solutions_and_versioned_candidate_inputs_staged_not_deployed',utc=datetime.now(timezone.utc).isoformat(),source=source,wheel_metadata=candidate,solutions=reports,notices=[dict(path='third_party/python/defusedxml-0.7.1/'+Path(n).name,sha256=hashlib.sha256(b).hexdigest()) for n,b in notices.items()],target_platform='0.1.22',target_core='19.0.0.1.22',frozen_contract_files_changed=[],worker_changes=0,host_tooling_changes=0,limits=['Static wheel/complete solver review only; actual built image, installed metadata, nativeXLSX/entity/CRUD and approved maintenance/preservation remain required.','No source hooks or installation into active environment; all old distribution pins/hash blocks preserved byte-for-byte.','Specific entity mitigation, not all native Expat/SQLite CVEs fixed.'])
with (OUT/'static-resolution.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],packages={r['label']:r['target_packages'] for r in reports})))
