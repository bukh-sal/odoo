"""Clear exact observed source/history identities, never directory-wide rules."""
import hashlib,json
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-image-secret-audit-01'
def load(path):return json.loads(path.read_bytes())
prior=ROOT/'docs/evidence/G5/20261029-secret-scan-01/triage-source-image.json'
reviewed={(r['file_sha256'],r['offset'],r['rule'],r['fingerprint']):r['reason'] for r in load(prior)['records']}
extra={
 ('b715ef2481ce9920d9c6bff4f416b689bab7e1472ae325a746e1f3f230e59b50',2128,'credential-literal','7057d5276c3557401e2dc9ed'):'Prior scanner triage asserts the public psql variable-reference syntax; this is audit source, not a configured password.',
 ('85c5e8729d1517aada0b4afc025cb50d0c5d024ad700e954a6331aab6cec359a',2050,'credential-literal','52ba4f37a8d8f5372e63e163'):'Source expression repr(password) constructs a private stdin program at execution; no actual credential bytes in source.',
 ('980baf60ecf3c56d9c755a4767e2e3f46182d5f6603707a4a603022ce1df4486',1153,'credential-literal','49fa1b790a5c8894ee29017b'):'Intentionally wrong configuration literal for negative preflight; never a generated credential or active database value.',
 ('74d9e19d6ab5acc8c74493063f4a8e0f7f99bc00fdcec776350e7db09aa6e2d5',2233,'private-key-marker','0dd77d4390f097e4e56f4ec0'):'Scanner regression specimen: PEM marker with synthetic non-key body, used only to prove scanner detection.',
 ('8c02e7845c36b97b852e8c6e600d1f8ea554d507832d6bcefc6f29691be4abca',6970,'credential-literal','e76d931dd26e7d05ced42582'):'Unit-test in-memory readiness callback uses a synthetic credential-change marker to assert review invalidation; no database connection or account.',
 ('aca2d8563d3df72af41afa0ee96348472351912c44710f20763fd2d10fd47d37',6733,'credential-literal','e76d931dd26e7d05ced42582'):'Earlier Git blob of the same synthetic in-memory readiness invalidation test; exact bytes/offset reviewed.'}
records=[];counts={}
for name in ['tracked-tree','implementation-history']:
 report=load(OUT/(name+'.json'));assert report['known_secret_findings']==0
 counts[name]=len(report['findings'])
 for finding in report['findings']:
  path=PRIVATE/'history-blobs'/finding['git_blob'] if 'git_blob' in finding else ROOT/finding['location']
  assert hashlib.sha256(path.read_bytes()).hexdigest()==finding['file_sha256']
  key=tuple(finding[k] for k in ['file_sha256','offset','rule','fingerprint'])
  reason=reviewed.get(key) or extra.get(key);assert reason,'Unreviewed exact finding identity'
  records.append(dict(**finding,report=name,disposition='reviewed_public_fixture_or_expression',reason=reason))
result=dict(result='passed_current_tracked_source_and_implementation_history_secret_review',source_head=report['source_head'],known_values=121,counts=counts,known_generated_findings=0,unreviewed_findings=0,prior_exact_review=dict(path=prior.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(prior.read_bytes()).hexdigest()),records=records,limits=['Current tracked tree and every implementation-introduced blob through captured HEAD only; current images, archives/assets/logs and new audit files remain separate.','Exact file SHA256/offset/rule/fingerprint reuse, not path-based suppression. No Git rewrite or publication.'])
with (OUT/'repository-triage.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],counts=counts,known_generated_findings=0,unreviewed_findings=0)))
