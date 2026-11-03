"""Current real binary upload bounds and existing native error service reuse."""
import ast,hashlib,importlib.util,json,socket,ssl,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).parent;ROOT=Path.cwd();LOCAL=ROOT/'.local/g7-production-profile-01'
spec=importlib.util.spec_from_file_location('current_upload_probe',OUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
state=json.loads((LOCAL/'state.json').read_text());fixture=json.loads((LOCAL/'fixtures.json').read_text());client=m.Client('production');client.login(state,fixture,'operator')
code,value,_,_=client.request('/api/v1/operations/catalog',headers={'Origin':client.origin,'X-MP-Client-Release':client.release});assert code==200 and value['data']['kind']=='catalog'
checks=[]
for size,csrf in [(16,True),(16,False),(11*1024*1024,True)]:
 raw=b'x'*size;assert len(raw)==size
 headers={'Origin':client.origin,'Content-Type':'application/octet-stream','X-MP-Client-Release':client.release,'X-MP-Artifact-Digest':'sha256:'+hashlib.sha256(raw).hexdigest()}
 if csrf:headers['X-CSRFToken']=client.csrf
 code,value,_,_=client.request('/api/v1/operations/validate-upload',raw=raw,headers=headers)
 assert code==(400 if csrf else 403),(size,csrf,code,value)
 checks.append(dict(bytes=size,csrf=csrf,status=code,validator_reached=csrf))
ctx=ssl.create_default_context(cafile=str(LOCAL/'server.crt'));bounds=[]
for path,length in [('/api/v1/operations/validate-upload',100*1024*1024+1),('/api/v1/workspace/settings',10*1024*1024+1)]:
 with socket.create_connection(('127.0.0.1',state['https_port']),timeout=10) as stream:
  with ctx.wrap_socket(stream,server_hostname='security.localhost') as conn:
   request=('POST '+path+' HTTP/1.1\r\nHost: '+client.authority+'\r\nOrigin: '+client.origin+'\r\nContent-Type: application/octet-stream\r\nContent-Length: '+str(length)+'\r\nConnection: close\r\n\r\n').encode();conn.sendall(request);raw=conn.recv(8192);assert raw.startswith(b'HTTP/1.1 413 ')
 bounds.append(dict(path=path,declared_length=length,status=413))
# Existing actual native source functions, actual CURRENT native429; old API
# DTO retained only as deliberately wrong-protocol input control, not as a new
# runtime observation. No replacement dialog/parser code is introduced.
tree=ast.parse((ROOT/'docs/evidence/G5/20261029-http-security-02/native_rate.py').read_text())
code=next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str) and n.value.value.startswith("const fs=require('fs')"))
code=code.replace('docs/evidence/G5/20261029-http-security-02/native-rate-example.json','docs/evidence/G7/20261104-production-profile-01/native-login-rate-example.json')
r=subprocess.run([r'C:\Program Files\nodejs\node.exe','-e',code],capture_output=True,timeout=20);(LOCAL/'native-error-parser.stdout').write_bytes(r.stdout);(LOCAL/'native-error-parser.stderr').write_bytes(r.stderr);assert r.returncode==0
native=json.loads(r.stdout)
old=json.loads((ROOT/'docs/evidence/G5/20261029-http-security-02/native-rate-qualification.json').read_text())
image=json.loads((ROOT/'.local/g7-release-runtime-audit-01/runtime-observation.json').read_text());inventory=image['inventory']['files']
for name,sha in old['native_source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha and inventory[name]==sha
record=dict(result='passed_current_upload_bounds_and_existing_native_error_reuse',utc=datetime.now(timezone.utc).isoformat(),application_image=state['image_id'],proxy_image='sha256:dece6f0a0402ab7187d5d0594056ad12fdbe1265c30f0e6134966e55c432828f',operator_catalog_access=True,upload_cases=checks,negative_header_bounds=bounds,native_error=native,native_source_sha256=old['native_source_sha256'],native_source_same_in_actual570_inventory=True,no_installation_or_approval=True,limits=['Actual current native429 reaches existing Odoo error/dialog service seam, not rendered Owl UI. OldAPI DTO is a static wrong-protocol control only.','Scoped invalid archives never install/approve a plugin; whole-release secret scanning and browser/accessibility remain separate.'])
(OUT/'upload-native-error-qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(result=record['result'],upload_cases=len(checks),header_bounds=len(bounds),native_handler=native)))
