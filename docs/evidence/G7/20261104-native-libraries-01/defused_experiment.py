"""Disposable library-only experiment; no active image or dependency-lock change."""
import base64,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-native-libraries-01'
source=json.loads((PRIVATE/'defusedxml-source.json').read_text());payload=(PRIVATE/source['filename']).read_bytes();assert hashlib.sha256(payload).hexdigest()==source['sha256']
image=json.loads((OUT/'inventory.json').read_text())['roles']['application']['image_id']
code="""import base64,hashlib,io,json,pathlib,sys
mode=sys.argv[1]
if mode=='protected':
 v=json.load(sys.stdin);raw=base64.b64decode(v['wheel']);assert hashlib.sha256(raw).hexdigest()==v['sha256'];p=pathlib.Path('/tmp/defusedxml.whl');p.write_bytes(raw);sys.path.insert(0,str(p))
import openpyxl
from openpyxl.xml import functions as f
xml=b'<!DOCTYPE root [<!ENTITY probe "probe_value">]><root>&probe;</root>'
try:
 nodes=list(f.iterparse(io.BytesIO(xml)));entity=dict(expanded=True,value=nodes[-1][1].text)
except Exception as error:entity=dict(expanded=False,exception=type(error).__name__)
book=openpyxl.Workbook();book.active['A1']='parser_probe';output=io.BytesIO();book.save(output);output.seek(0);read=openpyxl.load_workbook(output,read_only=True);assert read.active['A1'].value=='parser_probe';read.close()
print(json.dumps(dict(mode=mode,openpyxl=openpyxl.__version__,LXML=openpyxl.LXML,DEFUSEDXML=openpyxl.DEFUSEDXML,iterparse_module=f.iterparse.__module__,tiny_entity_input=entity,ordinary_XLSX_roundtrip=True)))
"""
rows=[]
for mode in ['baseline','protected']:
 args=['docker','run','--rm','-i','--name','mp-g7-defused-'+mode,'--label','com.modular.disposable=mp-g7-native-libraries','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','256m','--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=16m','--entrypoint','/venv/bin/python',image,'-B','-c',code,mode]
 r=subprocess.run(args,input=json.dumps(dict(wheel=base64.b64encode(payload).decode(),sha256=source['sha256'])).encode() if mode=='protected' else None,capture_output=True,timeout=45);(PRIVATE/('defused-'+mode+'.stdout')).write_bytes(r.stdout);(PRIVATE/('defused-'+mode+'.stderr')).write_bytes(r.stderr);assert r.returncode==0
 rows.append(json.loads(r.stdout))
assert rows[0]['tiny_entity_input']==dict(expanded=True,value='probe_value') and not rows[0]['DEFUSEDXML']
assert rows[1]['DEFUSEDXML'] and rows[1]['tiny_entity_input']==dict(expanded=False,exception='EntitiesForbidden') and rows[1]['ordinary_XLSX_roundtrip']
record=dict(result='existing_openpyxl_defused_support_stops_entity_input_preserves_workbook',utc=datetime.now(timezone.utc).isoformat(),actual_base_image=image,source=source,rows=rows,images_built=0,retained_helpers=0,active_deployments_changed=False,dependency_locks_changed=False,next_action='Inspect existing independently reviewed Python-maintenance path and stage exact defusedxml app dependency with required compatible/versioned release qualification; no custom parser.',limits=['Tiny benign entity declaration demonstrates actual parser selection and explicit refusal, not an exploit or proof all ExpatCVEs are fixed.','Wheel imports only in disposable no-network/no-config helpers; current app image remains without this candidate dependency.','Remaining vendor/CVE-specific reachability and full G7/security/reprobuild/release-kit still required.'])
with (OUT/'defused-experiment.json').open('x',encoding='utf8') as f:json.dump(record,f,indent=2)
print(json.dumps(dict(result=record['result'],baseline_entity_expanded=True,protected_refused=True,ordinary_XLSX_preserved=True)))
