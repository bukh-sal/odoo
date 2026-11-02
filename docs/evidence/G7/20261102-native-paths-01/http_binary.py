"""Live binary route on one exact disposable legacy row, removed in finally."""
import hashlib,importlib.util,json,sys,urllib.request,urllib.error
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
sp=importlib.util.spec_from_file_location('core18_current',OUT/'activate.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
import r1_probe
f,j=m.f,m.j;f.OUTPUT=OUT;r1_probe.r1.r0.LOCAL=j.LOCAL
state,native=m.context();assert native.config['generation']==25
private=j.LOCAL/'g7-native-paths-01';marker=private/'http-binary-marker.json';assert not marker.exists()
fixture=f.load(j.LOCAL/'fixtures.json');before=m.snapshot(state,'g7-http-binary-02-data-before')
name='G7-owned-legacy-'+uuid4().hex;body=('G7-synthetic-public-binary-'+uuid4().hex).encode()
note=next(r for r in before['mp_example_note'] if r['workspace_id']==fixture['workspaces']['A']['id'])
packet=dict(name=name,body=list(body),note_id=note['id'])
code="""import hashlib,json
p=PACKET
env.cr.execute("SELECT jsonb_object_agg(id::text,encode(sha256(convert_to(to_jsonb(a)::text,'UTF8')),'hex')) FROM ir_attachment a");before=env.cr.fetchone()[0]
body=bytes(p['body'])
env.cr.execute(\"\"\"INSERT INTO ir_attachment(name,res_model,res_id,type,public,db_datas,file_size,checksum,mimetype,create_uid,write_uid,create_date,write_date)
 VALUES(%s,'mp.example.note',%s,'binary',true,%s,%s,%s,'text/plain',1,1,timezone('UTC',now()),timezone('UTC',now())) RETURNING id\"\"\",[p['name'],p['note_id'],body,len(body),hashlib.sha1(body).hexdigest()])
ident=env.cr.fetchone()[0];env.cr.commit()
print('MP_LEGACY_HTTP='+json.dumps(dict(id=ident,before_hashes=before)))
""".replace('PACKET',repr(packet))
f.write(marker,dict(state='seeding_exact_legacy_fixture',name=name))
raw=f.native(state,'g7-http-binary-seed-02',[],code)
rows=[json.loads(line.split('MP_LEGACY_HTTP=',1)[1]) for line in raw.decode().splitlines() if line.startswith('MP_LEGACY_HTTP=')];assert len(rows)==1
record=dict(state='fixture_committed',**rows[0],name=name,body_sha256=hashlib.sha256(body).hexdigest());f.write(marker,record)
results=[]
try:
    alice=r1_probe.Client(state,fixture,'alice')
    for case,opener,headers in [('anonymous',urllib.request.build_opener(urllib.request.ProxyHandler({})),{}),
            ('same_workspace',alice.http,{'X-MP-Workspace':fixture['workspaces']['A']['public_id'],'X-MP-Client-Release':alice.release_token}),
            ('foreign_workspace',alice.http,{'X-MP-Workspace':fixture['workspaces']['B']['public_id'],'X-MP-Client-Release':alice.release_token})]:
        request=urllib.request.Request(alice.base+'/web/content/'+str(record['id']),headers=headers)
        try:response=opener.open(request,timeout=20)
        except urllib.error.HTTPError as error:response=error
        with response:status=response.code;data=response.read()
        results.append(dict(case=case,status=status,fixture_bytes_returned=body in data))
    assert all(r['status'] in (403,404) and not r['fixture_bytes_returned'] for r in results),results
finally:
    record['state']='cleaning_exact_fixture';f.write(marker,record)
    cleanup="""import hashlib,json
p=PACKET;body=bytes(p['body'])
env.cr.execute('SELECT name,res_model,res_id,db_datas,store_fname,public FROM ir_attachment WHERE id=%s',[p['id']]);row=env.cr.fetchone()
assert row and row[:3]==(p['name'],'mp.example.note',p['note_id']) and bytes(row[3])==body and row[4] is None and row[5] is True
env.cr.execute('DELETE FROM ir_attachment WHERE id=%s AND name=%s',[p['id'],p['name']]);assert env.cr.rowcount==1;env.cr.commit()
env.cr.execute("SELECT jsonb_object_agg(id::text,encode(sha256(convert_to(to_jsonb(a)::text,'UTF8')),'hex')) FROM ir_attachment a");after=env.cr.fetchone()[0];assert all(after.get(k)==v for k,v in p['before_hashes'].items())
print('MP_LEGACY_CLEANED=1')
""".replace('PACKET',repr(dict(packet,**rows[0])))
    raw=f.native(state,'g7-http-binary-clean-02',[],cleanup);assert b'MP_LEGACY_CLEANED=1' in raw
    record['state']='fixture_removed';f.write(marker,record)
assert m.snapshot(state,'g7-http-binary-02-data-after')==before
f.save('http-binary.json',dict(result='passed_actual_legacy_public_binary_HTTP_denials',cases=results,native_generation=25,
    exact_synthetic_fixture_created_and_removed=True,all_original_attachment_metadata_exact=True,no_filestore_write=True,all36jobs_other16tables_exact=True,
    token_and_limited_field_shortcuts_tested_in_native_results=True,limits='Live HTTP public shortcut tested without secret query tokens; native suite exercises real ordinary and limited field tokens.'))
print('Live anonymous/own/foreign legacy binary routes denied; exact synthetic row removed, original metadata/data unchanged')
