"""ADR0051's declared schema, fixtures and guard consumers; unrelated hashes fixed."""
import hashlib
import json
from pathlib import Path

root=Path.cwd();path=root/'docs/contracts/freeze-v1.json'
freeze=json.loads(path.read_text())
assert freeze['revision']==17 and len(freeze['files'])==101 and len(freeze['contracts'])==8
changed=['packages/contracts/v1/lifecycle-impact.schema.json']
added=['packages/contracts/examples/v1/lifecycle-impact/dispatch-base.json',
       'packages/contracts/examples/v1/lifecycle-impact/dispatch-events.json',
       'docs/architecture-decisions/0051-native-uninstall-dispatch-integration.md',
       'tests/test_lifecycle_contracts.py','tests/test_native_uninstall.py']
for name,digest in freeze['files'].items():
    if name not in changed:
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
assert all(name not in freeze['files'] for name in added)
row=next(row for row in freeze['contracts'] if changed[0] in row['paths'])
row['paths'].extend(added)
for name in changed+added:
    freeze['files'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
freeze['revision']=18
path.write_text(json.dumps(freeze,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(revision=18,files=len(freeze['files']),changed=changed,added=added)))
