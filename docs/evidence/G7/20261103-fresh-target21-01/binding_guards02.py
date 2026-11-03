"""Actual current v1/v2 named selection and missing/mismatch refusal."""
import json,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import ROOT,OUT,LOCAL,f,context,snapshot
from modular_platform.catalog import Catalog
from modular_platform.worker_operator import operator_observer
import r1_probe
from modular_platform.contracts import ERROR_STATUS
state,native=context('connector');record=f.load(LOCAL/'fresh-smoke/state.json');assert record['state']=='qualified'
f.OUTPUT=OUT/'fresh-smoke';fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;client=r1_probe.Client(state,fixture,'alice')
before=snapshot(state,'fresh-binding02-before');obs=native.observer.read();doc=native.observer.state(obs,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
wid=fixture['workspaces']['A']['public_id'];entries=[b for b in doc['bindings'] if b['workspace_id']==wid and b['service_id']=='org.example.notes.documents']
v1=next(b for b in entries if b['api_version']=='1.0' and b['alias']=='documents');v2=next(b for b in entries if b['api_version']=='2.0' and b['alias']=='documents')
note=record['A_note'];results=[]
for label,version,values,binding,positive in [('v1','1.0',dict(note_id=note['id']),v1,True),('v2','2.0',dict(document_id=note['id']),v2,True),('v2_wrong_v1_binding','2.0',dict(document_id=note['id']),v1,False),('v2_missing_binding','2.0',dict(document_id=note['id']),None,False)]:
 headers={'X-CSRFToken':client.csrf}
 if binding:headers['X-MP-Binding']=binding['binding_id']
 code,value=client.request('/api/v1/services/org.example.notes.documents/get',dict(api_version=version,request_id=str(uuid4()),input=values),'A',headers)
 f.write(LOCAL/'fresh-smoke'/(label+'-wire-status.json'),dict(case=label,status=code,error_code=value.get('error',{}).get('code')))
 if positive:
  assert code==200 and 'data' in value
  assert value['data']['id' if version=='1.0' else 'document_id']==note['id']
 else:
  error=value.get('error',{}).get('code');assert error in {'VALIDATION_FAILED','FORBIDDEN','NOT_FOUND','CONFLICT','DEPENDENCY_UNAVAILABLE','UNAUTHENTICATED'} and code==ERROR_STATUS[error] and value.get('data') is None and 'traceback' not in json.dumps(value).lower()
 results.append(dict(case=label,status=code,error_code=value.get('error',{}).get('code')))
assert snapshot(state,'fresh-binding02-after')==before
f.save('binding-guards.json',dict(result='passed_actual_fresh_named_v1_v2_and_missing_mismatch_denials',cases=results,no_latest_fallback=True,all17tables_exact=True,acceptance='API-06',scope='Current actual binding selection with explicit major-specific DTOs; prior unchanged resolver/missing-provider vectors retained separately.'))
print(json.dumps(dict(result='fresh_binding_guards_passed',cases=results)))
