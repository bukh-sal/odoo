"""Preserve notices from the exact retained independently qualified worker image."""
import base64,hashlib,io,json,re,zipfile
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-core22-provenance-01'
def load(p):return json.loads(p.read_bytes())
def sha(raw):return hashlib.sha256(raw).hexdigest()
prior=ROOT/'docs/evidence/G7/20261103-release-runtime-audit-01'
index=load(prior/'worker-index.json');binding=load(prior/'worker-source-binding.json')
current=load(ROOT/'docs/evidence/G7/20261104-offline-runtime-01/qualification.json')
assert current['containers'][1]['image']==index['image_id']
raw=(ROOT/'.local/g7-release-runtime-audit-01/worker-collection.stdout').read_bytes()
assert sha(raw)==index['raw_notice_bundle_sha256']
data=json.loads(raw);assert data['worker_source_files']==index['worker_source_files']
pins={re.sub('[-_.]+','-',n).lower():v for n,v in re.findall(r'^([A-Za-z0-9_.-]+)==([^\s\\;]+)',(ROOT/'services/document_stats/requirements.lock').read_text(),re.M)}
assert {re.sub('[-_.]+','-',p['name']).lower():p['version'] for p in data['python']}==pins and len(pins)==13
assert all(p['notices'] for p in data['python']) and all(p['copyright'] for p in data['os_packages'])
archive=io.BytesIO();rows=[]
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for name,item in sorted(data['notices'].items()):
  value=base64.b64decode(item['base64']);assert sha(value)==item['sha256']
  name='worker'+name;z.writestr(name,value);rows.append(dict(path=name,sha256=sha(value),bytes=len(value)))
value=archive.getvalue();path=PRIVATE/'worker-notices.zip';assert not path.exists();path.write_bytes(value)
record=dict(result='passed_exact_retained_worker_notice_preservation',image_id=index['image_id'],python_distributions=13,OS_packages=len(data['os_packages']),files=rows,archive_sha256=sha(value),source_collection_sha256=sha(raw),source_binding=dict(path=(prior/'worker-source-binding.json').relative_to(ROOT).as_posix(),sha256=sha((prior/'worker-source-binding.json').read_bytes())),current_identity_observation='../20261104-offline-runtime-01/qualification.json',limits=['Exact image-bound previously collected notice bytes preserved, not a redundant worker rebuild or fresh source collection.','No vulnerability waiver, commercial licensing conclusion or full OPS03/release pass.'])
with (OUT/'worker-notice-bundle.json').open('x',encoding='utf8') as stream:json.dump(record,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=record['result'],Python=13,OS=record['OS_packages'],notices=len(rows))))

