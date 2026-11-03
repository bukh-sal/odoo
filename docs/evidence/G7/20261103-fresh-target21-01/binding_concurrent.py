"""Actual simultaneous v1/v2 named reads in independent authenticated sessions."""
import json,sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).parent))
from lifecycle import OUT,LOCAL,f,context,snapshot
from modular_platform.catalog import Catalog
import r1_probe
state,native=context('connector');f.OUTPUT=OUT/'fresh-smoke';record=f.load(LOCAL/'fresh-smoke/state.json');assert record['state']=='qualified'
fixture=f.load(LOCAL/'fixtures.json');r1_probe.r1.r0.LOCAL=LOCAL;obs=native.observer.read();doc=native.observer.state(obs,Catalog(native.catalog_root,native.validator,readonly=True).snapshot())['state']
wid=fixture['workspaces']['A']['public_id'];bindings={version:next(b for b in doc['bindings'] if b['workspace_id']==wid and b['service_id']=='org.example.notes.documents' and b['alias']=='documents' and b['api_version']==version) for version in ('1.0','2.0')}
clients={version:r1_probe.Client(state,fixture,'alice') for version in bindings}
before=snapshot(state,'fresh-concurrent-bindings-before')
def read(version):
 client=clients[version];field='note_id' if version=='1.0' else 'document_id'
 code,value=client.request('/api/v1/services/org.example.notes.documents/get',dict(api_version=version,request_id=str(uuid4()),input={field:record['A_note']['id']}),'A',{'X-CSRFToken':client.csrf,'X-MP-Binding':bindings[version]['binding_id']})
 assert code==200 and value['data']['id' if version=='1.0' else 'document_id']==record['A_note']['id']
 return dict(version=version,status=code,fields=sorted(value['data']))
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(read,['1.0','2.0']))
assert snapshot(state,'fresh-concurrent-bindings-after')==before
f.save('binding-concurrent.json',dict(result='passed_actual_simultaneous_named_v1_v2_reads',independent_authenticated_sessions=2,results=results,all17tables_exact=True))
print('Simultaneous actual v1/v2 requests returned their declared distinct DTOs; all17tables exact')
