"""Exact image finding review; parser constants/docs are not private identities."""
import ast,hashlib,json,sys,re
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
def load(path):return json.loads(path.read_bytes())
prior=ROOT/'docs/evidence/G5/20261029-secret-scan-01/triage-source-image.json'
known={tuple(r[k] for k in ['file_sha256','offset','rule','fingerprint']):r['reason'] for r in load(prior)['records']}
report=load(OUT/'image-layers.json');assert report['known_secret_findings']==0 and len(report['findings'])==83
source_sha='162b177bf9d429d3c67ea10d5612a99a86b399a23ca87f067be5466dcd1dca4c'
source=(PRIVATE/'finding-files'/source_sha).read_bytes();assert hashlib.sha256(source).hexdigest()==source_sha
marker=b'-----BEGIN '+b'OPENSSH PRIVATE KEY-----'
tree=ast.parse(source);assert any(isinstance(node,ast.Constant) and node.value==marker for node in ast.walk(tree))
url_sources=['b117515dddf2799d7ebca975af25a72b5e4802741c211ee18c4196227598583c','6a2814d91987dd9728278d413a154ee5277b15cb262d9945425377f2a693311f']
sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import RULES
for digest,offset in zip(url_sources,[8121,8104]):
 raw=(PRIVATE/'finding-files'/digest).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest
 parsed=ast.parse(raw);function=next(n for n in ast.walk(parsed) if isinstance(n,ast.FunctionDef) and n.name=='url')
 match=re.compile(RULES['credential-url']).match(raw,offset);assert match and match.group().decode() in ast.get_docstring(function)
extra={
 ('494e88c528ff23eebfcba159359250877939501d0b96087b3a7069b5f21d274d',2826,'private-key-marker','21f798e70ba77d24e051025d'):'Pinned cryptography SSH serialization compiled constant; source AST independently verifies the format-marker constant, not a configured private key.',
 (source_sha,1980,'private-key-marker','21f798e70ba77d24e051025d'):'Pinned cryptography SSH serialization source contains the PEM boundary as a bytes constant for format parsing; no key body or platform private identity.',
 ('7ad0e432473b7e0de53ce18f05b5c208d6a9239e69376a868314a5ba05971a9b',7849,'credential-url','4dab902678fbe605d8b41400'):'Pinned pip-vendored urllib3 compiled Url.url property documentation example; source function docstring independently checked.',
 (url_sources[0],8121,'credential-url','4dab902678fbe605d8b41400'):'Pinned pip-vendored urllib3 Url.url property function documentation example; not a configured proxy connection.',
 ('25b751c7756cf11e0cf15dd2512b3f23fbba3facc57dd17152f543bc7325c963',2826,'private-key-marker','21f798e70ba77d24e051025d'):'Application copy of the same cryptography SSH format constant in compiled code; exact source bytes match independently reviewed parser source.',
 ('6234036ca8d99e9017a7af773db80746d7a72292a8b736e3cd5a6734c9e3b7ee',7849,'credential-url','4dab902678fbe605d8b41400'):'Application copy of pip-vendored urllib3 compiled Url.url property documentation; exact source example independently checked.',
 ('e68072600c95a3ebfdeae94af2ca450d9da6a452a85ddb122d3eda37bbe3136c',7820,'credential-url','4dab902678fbe605d8b41400'):'Installed urllib3 compiled Url.url property documentation example; exact source function docstring checked.',
 (url_sources[1],8104,'credential-url','4dab902678fbe605d8b41400'):'Installed urllib3 Url.url property documentation example; not a configured credential.'}
records=[]
for finding in report['findings']:
 raw=(PRIVATE/'finding-files'/finding['file_sha256']).read_bytes();assert hashlib.sha256(raw).hexdigest()==finding['file_sha256']
 key=tuple(finding[k] for k in ['file_sha256','offset','rule','fingerprint']);reason=known.get(key) or extra.get(key);assert reason,'Unreviewed exact finding'
 records.append(dict(**finding,reason=reason,disposition='reviewed_vendor_fixture_format_constant_or_documentation'))
result=dict(result='passed_current_all_unique_image_layers_and_metadata_secret_review',images=report['images'],unique_layers=report['unique_layers'],files=report['files'],bytes=report['bytes'],known_values=121,known_generated_findings=0,reviewed_generic_findings=len(records),unreviewed_findings=0,prior_exact_review_sha256=hashlib.sha256(prior.read_bytes()).hexdigest(),records=records,limits=['All exported regular members including hidden/deleted lower-layer files and image config/history metadata; exact file SHA256/offset/rule/fingerprint review.','Vendor test keys/snakeoil and parser/documentation literals remain explicitly identified by original exact-content review; they are not active platform identities.','Native dependencies remain trusted code; no universal secret detector or vulnerability-free image claim.'])
with (OUT/'image-triage.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],layers=report['unique_layers'],files=report['files'],reviewed=len(records),known=0)))
