"""Rollback-only legacy attachment counterexample on the installed image."""
import hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('native_current',ROOT/'docs/evidence/G6/20261102-notes-stats-ui-source-01/upgrade.py')
m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
base,f,j=m.base,m.f,m.j;f.OUTPUT=OUT
state,native=m.context();before=base.snapshot(state,'g7-attachment-probe-before')
code='''import hashlib,json,uuid
from odoo import api
from odoo.exceptions import AccessError
env.cr.rollback()
env.cr.execute('SELECT count(*) FROM ir_attachment');before=env.cr.fetchone()[0]
payload=('G7-disposable-legacy-attachment-'+uuid.uuid4().hex).encode();token=uuid.uuid4().hex
env.cr.execute('SELECT id FROM mp_example_note ORDER BY id LIMIT 1');note=env.cr.fetchone()[0]
try:
 env.cr.execute("""INSERT INTO ir_attachment(name,res_model,res_id,type,public,access_token,db_datas,file_size,checksum,mimetype,create_uid,write_uid,create_date,write_date)
 VALUES(%s,'mp.example.note',%s,'binary',true,%s,%s,%s,%s,'text/plain',1,1,timezone('UTC',now()),timezone('UTC',now())) RETURNING id""",
 ['G7 rollback-only legacy attachment',note,token,payload,len(payload),hashlib.sha1(payload).hexdigest()]);ident=env.cr.fetchone()[0]
 public=api.Environment(env.cr,env.ref('base.public_user').id,{})
 result={}
 for mode in ['public','token']:
  if mode=='token':env.cr.execute('UPDATE ir_attachment SET public=false WHERE id=%s',[ident]);env.invalidate_all(flush=False)
  try:
   record=public['ir.binary']._find_record(res_model='ir.attachment',res_id=ident,access_token=token if mode=='token' else None)
   stream=public['ir.binary']._get_stream_from(record,'raw')
   result[mode+'_shortcut_returned_fixture_bytes']=stream.data==payload
  except AccessError:result[mode+'_shortcut_returned_fixture_bytes']=False
finally:
 env.cr.rollback();env.invalidate_all(flush=False)
env.cr.execute('SELECT count(*) FROM ir_attachment');assert env.cr.fetchone()[0]==before
print('MP_ATTACHMENT_PROBE='+json.dumps(dict(result,all_fixture_rows_rolled_back=True,no_filestore_write=True,actual_native_binary_adapter=True)))
'''
raw=f.native(state,'g7-attachment-counterexample-01',[],code)
rows=[json.loads(line.split('MP_ATTACHMENT_PROBE=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_ATTACHMENT_PROBE=')];assert len(rows)==1
assert base.snapshot(state,'g7-attachment-probe-after')==before
result=rows[0]
f.save('attachment-counterexample.json',dict(result='counterexample_confirmed' if any(result[k] for k in result if k.endswith('_bytes')) else 'denied_as_required',
    **result,native_generation=24,image=state['image_id'],all36jobs_other16tables_exact=True,
    source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['platform_addons/mp_core/attachments.py','odoo/addons/base/models/ir_binary.py','odoo/addons/base/models/ir_attachment.py']},
    limits=['Synthetic legacy/operator-imported attachment row inserted only inside a rolled-back transaction; no normal user could create it through the supported blocked create API.',
            'Exercises the exact native binary adapter/stream, not a live HTTP request. The public/token shortcut currently bypasses the intended scoped attachment gate.']))
print(json.dumps(result))
