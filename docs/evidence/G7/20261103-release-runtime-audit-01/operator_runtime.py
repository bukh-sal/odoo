"""Current operator wheel identity/advisories and nonmutating old-key compatibility."""
import hashlib,importlib.metadata,json,ssl,urllib.request
from pathlib import Path
from datetime import datetime,timezone
import cryptography
from cryptography.hazmat.backends.openssl.backend import backend
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-runtime-audit-01'
keydir=ROOT/'.local/g7-fresh-release-01/target21/worker-setup'
paths=[keydir/'issuer.pem',keydir/'public.pem'];before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
key=serialization.load_pem_private_key(paths[0].read_bytes(),password=None)
public=serialization.load_pem_public_key(paths[1].read_bytes())
message=b'modular-platform-operator-crypto50-compatibility-probe'
signature=key.sign(message,padding.PKCS1v15(),hashes.SHA256());public.verify(signature,message,padding.PKCS1v15(),hashes.SHA256())
assert before=={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
packages=sorted([dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions()],key=lambda d:d['name'])
queries=[dict(package=dict(ecosystem='PyPI',name=p['name']),version=p['version']) for p in packages]
request=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps(dict(queries=queries)).encode(),headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request,timeout=45) as response:raw=response.read()
(PRIVATE/'operator50-osv-response.json').write_bytes(raw);rows=json.loads(raw)['results'];assert len(rows)==len(queries) and not any(r.get('next_page_token') for r in rows)
record=dict(result='isolated_operator_maintained_old_key_compatible',utc=datetime.now(timezone.utc).isoformat(),cryptography=cryptography.__version__,bundled_openssl=backend.openssl_version_text(),stdlib_openssl=ssl.OPENSSL_VERSION,packages=packages,queries=queries,matches=rows,old_crypto42_generated_RSA_key_read_sign_verify=True,existing_key_files_unchanged=True,deployment_or_publication_mutations=0,lock_sha256=hashlib.sha256((ROOT/'deploy/requirements-tooling.lock').read_bytes()).hexdigest(),response_sha256=hashlib.sha256(raw).hexdigest(),limits=['Package advisory snapshot only; bundled native libraries require separate review. Test signature is not an approval or runtime token and was not sent or published.'])
assert cryptography.__version__=='50.0.2'
with (OUT/'operator50-runtime.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(crypto=record['cryptography'],bundled_openssl=record['bundled_openssl'],packages=len(packages),matches=sum(bool(r.get('vulns')) for r in rows),old_keys_unchanged=True)))
