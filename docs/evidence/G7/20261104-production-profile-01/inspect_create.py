"""Persist one exact owned test request before dispatch; capture refusal/result."""
import importlib.util,json,sys
from pathlib import Path
from uuid import uuid4
ROOT=Path.cwd();OUT=Path(__file__).parent;LOCAL=ROOT/'.local/g7-production-profile-01'
spec=importlib.util.spec_from_file_location('current_http_probe',OUT/'probe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s=json.loads((LOCAL/'state.json').read_text());f=json.loads((LOCAL/'fixtures.json').read_text());client=m.Client('production');client.login(s,f,'alice')
marker=LOCAL/'create-diagnostic.json';assert not marker.exists();record=dict(state='dispatching_owned_create',key='sec02-diag-'+uuid4().hex,title='SEC02_owned_'+uuid4().hex);marker.write_text(json.dumps(record,indent=2))
code,value,headers,raw=client.service(f,'create',dict(title=record['title'],body='Owned temporary CSRF acceptance fixture'),key=record['key'])
(LOCAL/'create-diagnostic-response.bin').write_bytes(raw);record.update(state='response_captured',status=code,result=value);marker.write_text(json.dumps(record,indent=2))
print(json.dumps(dict(status=code,error=value.get('error') if value else None,created=bool(value and value.get('data')))))
