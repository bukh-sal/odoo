"""Actual installed native XLSX reader and scoped ORM import, rollback only."""
import json,sys
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;sys.path.insert(0,str(OUT))
import activate as m
f=m.f;f.OUTPUT=OUT;state,native=m.context('connector');r=f.load(m.PRIVATE/'state.json');assert r['state']=='preservation_verified' and native.config['generation']==5
before=m.snapshot(state,'core22-import02-before');identity=m.worker(native,'core22-import02-worker-before');fixture=f.load(m.LOCAL/'fixtures.json')
code="""import io,json,zipfile
from odoo import api
from odoo.addons.mp_identity.scopes import scoped_environment
from defusedxml.common import EntitiesForbidden
import openpyxl
fixture=FIXTURE
checks=[]
env.cr.rollback()
try:
 actor=scoped_environment(api.Environment(env.cr,fixture['users']['alice']['id'],{}),fixture['workspaces']['A']['public_id'])
 book=openpyxl.Workbook();book.active.append(['title','body']);book.active.append(['Native protected import','Ordinary workbook data']);data=io.BytesIO();book.save(data);raw=data.getvalue()
 good=actor['base_import.import'].create({'res_model':'mp.example.note','file':raw,'file_name':'probe.xlsx','file_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
 count,rows=good._read_xlsx({});assert rows==[['title','body'],['Native protected import','Ordinary workbook data']];checks.append('real_native_XLSX_reader_ordinary_values_preserved')
 result=actor['mp.example.note'].load(['title','body'],rows[1:]);assert len(result['ids'])==1 and not result['messages'];note=actor['mp.example.note'].browse(result['ids']);assert note.workspace_id.public_id==fixture['workspaces']['A']['public_id'];checks.append('standard_scoped_native_ORM_import_succeeds')
 modified=io.BytesIO()
 with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(modified,'w',zipfile.ZIP_DEFLATED) as target:
  for item in source.infolist():
   content=source.read(item.filename)
   if item.filename=='xl/worksheets/sheet1.xml':
    assert b'Ordinary workbook data' in content
    content=content.replace(b'Ordinary workbook data',b'&probe;');declaration=b'<!DOCTYPE worksheet [<!ENTITY probe "Ordinary workbook data">]>'
    if content.startswith(b'<?xml'):
     end=content.index(b'?>')+2;content=content[:end]+declaration+content[end:]
    else:content=declaration+content
   target.writestr(item,content)
 bad=actor['base_import.import'].create({'res_model':'mp.example.note','file':modified.getvalue(),'file_name':'entity-probe.xlsx','file_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
 try:bad._read_xlsx({})
 except ValueError as error:
  assert isinstance(error.__cause__,EntitiesForbidden),type(error.__cause__).__name__;checks.append('real_native_XLSX_reader_rejects_benign_entity_declaration_with_existing_openpyxl_error_wrapper')
 else:raise AssertionError('Native XLSX entity declaration was accepted')
 print('CORE22_IMPORT='+json.dumps(dict(result='passed',checks=checks,DEFUSEDXML=openpyxl.DEFUSEDXML,fixtures_rolled_back=True)))
finally:env.cr.rollback()
""".replace('FIXTURE',repr(fixture))
args=['docker','run','--rm','-i','--name','mp-g7-core22-native-import02','--label','com.modular.disposable=mp-g7-core22-defused','--log-driver','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--network',state['project']+'_runtime','--memory','1024m','--tmpfs','/tmp','--mount','type=volume,source='+state['project']+'_appconfig,target=/run/secrets,readonly','--mount','type=volume,source='+state['project']+'_filestore,target=/var/lib/modular,readonly','--entrypoint','/venv/bin/python',r['image_id'],'odoo-bin','shell','-c','/run/secrets/odoo_config','-d',state['active_db'],'--no-http','--workers=0','--max-cron-threads=0']
raw=f.command('core22-native-import02',args,input=code.encode(),timeout=120);result=json.loads(next(line.split('CORE22_IMPORT=',1)[1] for line in raw.decode().splitlines() if line.startswith('CORE22_IMPORT=')))
assert m.snapshot(state,'core22-import02-after')==before and m.worker(native,'core22-import02-worker-after')==identity;f.guard(state)
f.save('native-import.json',dict(result='passed_installed_native_XLSX_and_scoped_import',image_id=r['image_id'],configuration_generation=5,checks=result,all17tables_worker_configs_exact=True,helper_removed=True,limits=['Small benign entity-input refusal and ordinary native import; not all Expat/nativeCVE coverage or broad hostile-file containment.','All test imports/records/events rolled back; native views remain default, no custom parser.']));print(json.dumps(result))
