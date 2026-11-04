"""Exact review of eight vendor-documentation/compiled-source structural matches."""
import ast,base64,hashlib,importlib.util,io,json,marshal,re,sys,tarfile,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-kit-privacy-01';sys.path.insert(0,str(ROOT/'tools'))
from secret_scan import Scanner,RULES
def load(p):return json.loads(p.read_bytes())
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
report=load(OUT/'kit-expanded-privacy.json');assert len(report['findings'])==8;reviewed=[]
with tarfile.open(ROOT/'.local/releases/r1-0.1.23/toolchain/python-windows.tar.gz') as archive:
 for finding in report['findings']:
  raw=(PRIVATE/'finding-bytes'/finding['file_sha256']).read_bytes();assert hashlib.sha256(raw).hexdigest()==finding['file_sha256']
  hits=scanner.inspect_bytes(raw,finding['location']);assert not any(h['rule']=='known-generated-secret' for h in hits)
  assert any((h['offset'],h['rule'],h['fingerprint'])==(finding['offset'],finding['rule'],finding['fingerprint']) for h in hits)
  item=dict(finding,decision='benign_upstream_static_example',evidence={})
  if finding['rule']=='private-key-marker':
   assert '/node_modules/npm/' in finding['location']
   context=raw[max(0,finding['offset']-200):finding['offset']+350]
   assert b'XXXX' in context and b'example' in context.lower()
   assert not re.search(rb'-----BEGIN (?:RSA |OPENSSH |EC |ENCRYPTED )?PRIVATE KEY-----\r?\n(?:[A-Za-z0-9+/=]+\r?\n)+-----END ',raw)
   item.update(reason='npm TLS key-format documentation/description uses XXXX placeholder lines; no complete PEM key. Four exact doc/source representations retained.')
   item['evidence'].update(example_word_and_XXXX_in_exact_context=True,complete_private_PEM_blocks=0)
  elif finding['location'].endswith('@npmcli/arborist/README.md'):
   match=next(m for m in re.finditer(RULES['credential-literal'],raw) if m.start()==finding['offset'])
   literal=re.search(rb'[\x22\x27]([^\x22\x27]*)[\x22\x27]$',match.group()).group(1);decoded=base64.b64decode(literal)
   assert b'password' in decoded.lower() and all(c in b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ !.,-_' for c in decoded)
   assert b'new Arborist' in raw and b'base64' in raw[match.start()-250:match.end()+250].lower()
   fence=raw.rfind(b'```',0,match.start());assert fence>=0 and raw.find(b'```',match.end())>=0
   item.update(reason='Arborist README fenced configuration example documents a base64-encoded password-placeholder phrase. README is documentation, not active credentials; none of the133 issued values match.')
   item['evidence'].update(fenced_Arborist_configuration_example=True,base64_password_placeholder_prose=True)
  else:
   path=finding['location'].split('python-windows.tar.gz/',1)[1]
   if path.endswith('.pyc'):
    source_path=path.rsplit('/__pycache__/',1)[0]+'/'+path.rsplit('/',1)[1].split('.cpython-',1)[0]+'.py';source=archive.extractfile(source_path).read()
    stream=io.BytesIO(raw[16:]);code=marshal.load(stream)
    assert raw[:4]==importlib.util.MAGIC_NUMBER and stream.tell()==len(raw)-16
    assert code==compile(source,code.co_filename,'exec',dont_inherit=True,optimize=0)
    item['evidence'].update(pyc_magic_matches_selected_Python=True,no_trailing_marshal_bytes=True,code_object_equals_compile_of_exact_bundled_source=True,source_sha256=hashlib.sha256(source).hexdigest())
   else:source=raw
   tree=ast.parse(source)
   if finding['rule']=='credential-url':
    match=next(m for m in re.finditer(RULES['credential-url'],raw) if m.start()==finding['offset']);value=urllib.parse.urlsplit(match.group().decode())
    assert value.username=='user'+'name' and value.password=='pass'+'word'
    docs=[(getattr(node,'name','module'),ast.get_docstring(node)) for node in ast.walk(tree) if isinstance(node,(ast.Module,ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))]
    owners=[name for name,text in docs if text and match.group().decode() in text];assert owners
    item.update(reason='urllib3 URL property documentation uses literal username/password placeholders. Compiled representation, where present, equals the bundled source; no code is executed for review.')
    item['evidence'].update(placeholder_userinfo=True,AST_docstring_owners=owners)
   else:
    assert path=='python/Lib/urllib/__pycache__/request.cpython-312.pyc'
    doc=ast.get_docstring(tree);assert 'Example usage:' in doc and 'authinfo.add_password' in doc
    source_matches=list(re.finditer(RULES['credential-literal'],source));assert source_matches and all(m.group().decode() in doc for m in source_matches)
    item.update(reason='CPython urllib.request module documentation contains a BasicAuth usage example. The exact compiled code object equals the bundled source; structural match is in the serialized documentation, not an issued account value.')
    item['evidence'].update(module_docstring_BasicAuth_example=True,source_credential_literals_confined_to_documentation=True)
  reviewed.append(item)
result=dict(result='reviewed_all_eight_exact_vendor_static_findings',utc=datetime.now(timezone.utc).isoformat(),known_values=len(values),known_generated_findings=0,unreviewed_findings=0,reviewed=reviewed,limits=['Each decision binds exact content hash, offset, rule and keyed fingerprint; no path/rule-wide exclusion or vendor-source modification.','Compiled code is parsed/compiled for equality, never executed. External credentials are never tested.','Final qualification still needs nested-member result and complete prior-proof hash reconciliation.'])
with (OUT/'kit-static-triage.json').open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=result['result'],findings=len(reviewed),known_generated_findings=0)))
