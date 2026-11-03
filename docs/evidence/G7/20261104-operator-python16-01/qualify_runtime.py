"""Actual isolated interpreter/pin solution and old-key compatibility before selection."""
import hashlib,importlib.metadata,json,platform,pyexpat,sqlite3,ssl,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-operator-python16-01'
assert sys.version_info[:3]==(3,12,16) and Path(sys.executable).resolve()==(ROOT/'.local/toolchain/operator-python16/Scripts/python.exe').resolve()
base=Path(sys.base_prefix).resolve();assert base.is_relative_to(ROOT/'.local/toolchain/python16')
source=json.loads((PRIVATE/'python16-source.json').read_text());packages=sorted([dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions()],key=lambda r:r['name']);old=json.loads((ROOT/'docs/evidence/G7/20261103-release-runtime-audit-01/operator50-runtime.json').read_text());assert packages==old['packages']
keydir=ROOT/'.local/g7-fresh-release-01/target21/worker-setup';paths=[keydir/'issuer.pem',keydir/'public.pem'];before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
key=serialization.load_pem_private_key(paths[0].read_bytes(),password=None);public=serialization.load_pem_public_key(paths[1].read_bytes());message=b'modular-platform-operator-python16-old-key-compatibility'
public.verify(key.sign(message,padding.PKCS1v15(),hashes.SHA256()),message,padding.PKCS1v15(),hashes.SHA256());assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
core={}
for name in ['python.exe','python312.dll','LICENSE.txt','LICENSE','Lib/ssl.py','Lib/tarfile.py','Lib/tempfile.py','DLLs/pyexpat.pyd','DLLs/_sqlite3.pyd','DLLs/_ssl.pyd','DLLs/libcrypto-3.dll','DLLs/libssl-3.dll']:
 p=base/name
 if p.is_file():core[name]=dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
assert 'python.exe' in core and 'python312.dll' in core and any(n.startswith('LICENSE') for n in core)
previous=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-X','utf8','-c','import json,sys,ssl;print(json.dumps(dict(Python=sys.version.split()[0],stdlib_OpenSSL=ssl.OPENSSL_VERSION)))'],capture_output=True,check=True);old_runtime=json.loads(previous.stdout);assert old_runtime['Python']=='3.12.15'
q=json.loads((OUT/'qualification.json').read_text());assert q['result']=='passed' and sum(r['tests'] or 0 for r in q['records'])==232
record=dict(result='passed_isolated_Python16_exact_unchanged_packages_old_keys_and232consumers',utc=datetime.now(timezone.utc).isoformat(),Python=platform.python_version(),environment='.local/toolchain/operator-python16',interpreter='.local/toolchain/operator-python16/Scripts/python.exe',stdlib=dict(Expat=pyexpat.EXPAT_VERSION,SQLite=sqlite3.sqlite_version,OpenSSL=ssl.OPENSSL_VERSION),crypto_bundled_OpenSSL=backend.openssl_version_text(),packages=packages,package_versions_unchanged=True,old_RSA_read_sign_verify=True,old_keys_bytes_unchanged=True,old_environment_retained=old_runtime,source=source,core_interpreter_files=core,global_python_PATH_registry_change=False,installer_flags=['--install-dir project-owned','--no-bin','--no-registry','exact3.12.16','pinned_official_Astral_JSON_metadata'],consumer_qualification='qualification.json',checks=232,typescript='passed',freeze=dict(result='passed',files=101,rows=8,revision=17),limits=['Trusted binary installer uses pinned official Astral metadata/archive SHA; no global/shared interpreter replacement.','VendorPython3.12.16 security maintenance, not a blanket native-library/advisory/G7 pass. Expat2.10.0 and SQLite reachability/vendor review remain.','No application/worker image, endpoint, key, publication, schema, approval or native lifecycle mutation.'])
with (OUT/'runtime-qualification.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],Python=record['Python'],stdlib=record['stdlib'],checks=232,packages=len(packages))))
