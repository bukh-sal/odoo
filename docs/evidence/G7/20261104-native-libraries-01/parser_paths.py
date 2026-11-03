"""Bound direct native XML/SQLite imports and actual standard XLSX parser selection."""
import hashlib,inspect,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-libraries-01'
rows=json.loads((PRIVATE/'native_import_paths.json').read_text());runtime=json.loads((ROOT/'.local/g7-release-runtime-audit-01/runtime-observation.json').read_text());inventory=runtime['inventory']['files']
for row in rows:row['image_source_sha256']=inventory[row['image_path']]
code="""import functools,inspect,io,json
import openpyxl
from openpyxl.xml import functions as f
function=f.fromstring.func if isinstance(f.fromstring,functools.partial) else f.fromstring
book=openpyxl.Workbook();book.active['A1']='parser_probe';output=io.BytesIO();book.save(output);output.seek(0);read=openpyxl.load_workbook(output,read_only=True);assert read.active['A1'].value=='parser_probe';read.close()
print(json.dumps(dict(openpyxl=openpyxl.__version__,LXML=openpyxl.LXML,DEFUSEDXML=openpyxl.DEFUSEDXML,fromstring_module=function.__module__,iterparse_module=f.iterparse.__module__,iterparse_signature=str(inspect.signature(f.iterparse)),actual_minimal_XLSX_roundtrip=True)))
"""
image=json.loads((OUT/'inventory.json').read_text())['roles']['application']['image_id'];args=['docker','run','--rm','--name','mp-g7-parser-paths-01','--label','com.modular.disposable=mp-g7-native-libraries','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16m','--entrypoint','/venv/bin/python',image,'-B','-c',code]
r=subprocess.run(args,capture_output=True,timeout=45);(PRIVATE/'parser-paths.stdout').write_bytes(r.stdout);(PRIVATE/'parser-paths.stderr').write_bytes(r.stderr);assert r.returncode==0
actual=json.loads(r.stdout)
record=dict(result='direct_native_imports_and_actual_XLSX_parser_paths_recorded_review_pending',utc=datetime.now(timezone.utc).isoformat(),image=image,direct_imports=rows,XLSX=actual,context=dict(odoo_service_db='ElementTree parses the pinned installed res_country_data.xml during database bootstrap; source SHA in inventory.',odoo_test_reports='minidom parses native view architecture in the test report helper; production test endpoints/modes are separately disabled.',SQLite='Direct selected source imports in catalog.py/operator_store.py; private OS operator stores, not a public SQL execution API.'),limits=['Direct AST imports are not an exhaustive dynamic/transitive reachability proof.','Defused entity/externals defaults and selected lxml parser are actual observations, not a blanket fix for all Expat/native-library CVEs.','No malicious payload or safety-bound relaxation; full vendor/CVE-specific supported path review still pending.'])
with (OUT/'parser-paths.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(actual))
