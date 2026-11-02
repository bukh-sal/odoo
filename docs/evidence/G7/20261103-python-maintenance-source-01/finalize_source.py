"""Bind passing source consumers to the reviewed revision16 checkpoint."""
import hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent
qualified=json.loads((OUT/'qualification.json').read_text());linux=json.loads((OUT/'linux-consumers02.json').read_text())
assert qualified['result']==linux['result']=='passed'
assert sum(row['tests'] or 0 for row in qualified['records'])==180 and linux['tests']==65
for name,digest in qualified['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
base='af5db9dc'
before=json.loads(subprocess.check_output(['git','show',base+':docs/contracts/freeze-v1.json']))
after=json.loads((ROOT/'docs/contracts/freeze-v1.json').read_text());assert before['revision']==15 and after['revision']==16
changed=[name for name,digest in before['files'].items() if after['files'].get(name)!=digest]
added=sorted(after['files'].keys()-before['files'].keys());assert len(added)==3 and len(after['files'])==100
assert set(changed)=={'docs/contracts/protocol-v1.md','tests/test_contracts.py'}
assert not before['files'].keys()-after['files'].keys()
assert all(after['files'][name]==hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in after['files'])
schema_examples=[name for name in before['files'] if name.startswith('packages/contracts/')]
assert all(before['files'][name]==after['files'][name] for name in schema_examples)
record=dict(gate='G2',result='passed',utc=datetime.now(timezone.utc).isoformat(),contract_major=1,revision=16,frozen_files=100,rows=8,
 inventory_sha256=hashlib.sha256((ROOT/'docs/contracts/freeze-v1.json').read_bytes()).hexdigest(),git_base=qualified['git_base'],
 source_qualification='docs/evidence/G7/20261103-python-maintenance-source-01/qualification.json',
 linux_qualification='docs/evidence/G7/20261103-python-maintenance-source-01/linux-consumers02.json',
 host_checks=180,linux_checks=65,typescript='passed',freeze='passed',
 previous_revision=15,previous_files_retained_exactly=len(before['files'])-len(changed),changed_previous_files=changed,added_files=added,
 old_schema_example_files_unchanged=len(schema_examples),
 change='ADR0046: independently staged versioned Python maintenance with complete solution, one reviewed PDF successor, exact dependency review/hash and unchanged public DTO schemas.',
 runtime_qualification='Installed image31/core20 remains unchanged. Core21/SDK21 source only; exact dependency lock, release build, registry/lifecycle/recovery/worker/security/fresh release remain unqualified.')
gate=ROOT/'docs/evidence/G2/20261103-python16';gate.mkdir()
with (gate/'gate-G2.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2);f.write('\n')
with (OUT/'checkpoint.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2);f.write('\n')
print(json.dumps({k:record[k] for k in ['result','revision','frozen_files','host_checks','linux_checks','previous_files_retained_exactly','old_schema_example_files_unchanged']}))
