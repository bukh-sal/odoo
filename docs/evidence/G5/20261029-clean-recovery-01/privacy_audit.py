"""Incremental SEC03 check of changed source/evidence and new private diagnostics."""
import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]; OUTPUT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from clean_recovery_fixture import LOCAL, load, save
from clean_recovery_data import context
from modular_platform.native_executor import NativeExecutor
from modular_platform.operator_store import OperatorStore
from modular_platform.restore_executor import RestoreExecutor
from modular import configuration
from secret_scan import Scanner

state,target,reader,document,fixture=context()
old=ROOT/'.local/g5-secret-scan'
values={k:base64.b64decode(v) for k,v in load(old/'known-values.json').items()}
for p in LOCAL.iterdir():
    if p.is_file() and (p.name.endswith('password') or p.name.endswith('secret') or p.name=='service-token'):
        value=p.read_bytes().strip()
        if len(value)>=16:values['clean/'+p.name]=value
for actor,record in load(LOCAL/'session.json').items():
    values['clean/session/'+actor]=record['session_id'].encode()
recovery=RestoreExecutor(NativeExecutor(OperatorStore(LOCAL/'operator/control'), LOCAL/'operator/target.json',LOCAL/'operator/catalog',configuration(LOCAL/'operator/trust.json')))
_,private=recovery._authority(state['active_db'])
for user in private['users']:
    for field in ['password','totp_secret']:
        value=user[field]
        if value and len(value)>=16:values['clean/native/'+str(user['id'])+'/'+field]=value.encode()
scanner=Scanner((old/'fingerprint-key').read_bytes(),values)
names=subprocess.check_output(['git','ls-files','--modified','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
paths=[ROOT/n.decode() for n in names if n and (ROOT/n.decode()).is_file()]
findings=[]
for p in paths:findings.extend(scanner.inspect_file(p,p.relative_to(ROOT).as_posix()))
known=[f for f in findings if f['rule']=='known-generated-secret']
assert not known,'Generated material in public changed files; inspect redacted findings privately'
triage=[]
for f in findings:
    data=(ROOT/f['location']).read_bytes()
    assert f['location']=='tests/test_restore_dispatch.py' and f['rule']=='credential-literal'
    match=scanner.generic[f['rule']].match(data,f['offset'])
    assert match and b'post-review-revoked-credential' in match.group()
    triage.append(dict(**f,file_sha256=hashlib.sha256(data).hexdigest(),reason='Static synthetic unit-test replacement string, never an installed credential; exact file/offset/fingerprint reviewed.'))
diagnostics=list((LOCAL/'logs').glob('*'))
diagnostic_findings=[]
for p in diagnostics:
    if p.is_file():diagnostic_findings.extend(scanner.inspect_file(p,'private-diagnostic/'+p.name))
assert not diagnostic_findings,'New private diagnostic contains credential signatures; inspect locally'
containers=subprocess.check_output(['docker','ps','-a','--filter','label=com.modular.operation='+load(LOCAL/'fault-operation.json')['operation_id'],'--format','{{.ID}}']).decode().split()
for cid in containers:
    info=json.loads(subprocess.check_output(['docker','inspect',cid]))[0]
    assert info['HostConfig']['LogConfig']['Type']=='none'
save(sys.argv[1] if len(sys.argv)>1 else 'privacy-audit.json',dict(result='passed',changed_public_files=len(paths),known_credential_sources=len(values),known_secret_findings=0,generic_findings_reviewed=triage,private_diagnostics=len(diagnostics),private_diagnostic_findings=0,operation_children_without_daemon_logging=len(containers),source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},limits=['Incremental changed-source/evidence/private-log audit; prior full SEC03 tree/history/image/artifact audit retained.','Dedicated credential/config/checkpoint/recovery-kit stores are owner-protected inputs, not diagnostic/deliverable content.','No current raw native authentication material appears in public evidence/reviews.']))
print(json.dumps(dict(result='passed',public_files=len(paths),private_diagnostics=len(diagnostics),known_sources=len(values))))
