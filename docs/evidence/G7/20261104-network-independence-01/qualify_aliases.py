"""Qualify broader alias dispositions and actual current CSS remote-resource use."""
import base64,hashlib,json,re,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path.cwd();OUT=Path(__file__).parent
def load(p):return json.loads(p.read_bytes())
base=load(OUT/'backend-qualification.json');extension=load(OUT/'extended-hosts-and-CSS.json');record=load(ROOT/'.local/g7-ui-qualification-01/browser-input.json');assert extension['image']==base['image']==record['image_id']
families={r['path'] for r in extension['records'] if '/i18n/' not in r['path']}
assert families=={'addons/web/static/fonts/fonts.scss','addons/web/static/tests/views/fields/url_field.test.js'}
assert {h for r in extension['records'] for m in r['matches'] for h in m['hosts']}=={'fonts.odoocdn.com','odoo','service.odoo.co.in'}
assert extension['remote_font_declaring_bundles']==['web.report_assets_common']
origin=urlsplit(record['base']);opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));css=[]
for before in extension['production_CSS']:
 request=urllib.request.Request('http://127.0.0.1:'+str(origin.port)+before['path'],headers={'Host':origin.netloc})
 with opener.open(request,timeout=15) as response:data=response.read();assert response.status==200
 assert hashlib.sha256(data).hexdigest()==before['sha256']
 remote_urls=re.findall(rb'''(?i)url\(\s*["']?(https?://[^"')\s]+)''',data)
 remote_imports=re.findall(rb'''(?i)@import\s+["'](https?://[^"']+)''',data)
 assert not remote_urls and not remote_imports
 css.append(dict(path=before['path'],sha256=before['sha256'],remote_CSS_URL_resources=0,remote_CSS_imports=0,W3C_namespace_strings_are_not_resource_requests=True))
sys.path.insert(0,str(ROOT/'tools'));from secret_scan import Scanner
values={k:base64.b64decode(v) for k,v in load(ROOT/'.local/release-kit-rehearsal/private/reference/qualification-known-values-worker.json').items()};scanner=Scanner((ROOT/'.local/g5-secret-scan/fingerprint-key').read_bytes(),values)
paths=[p for p in OUT.iterdir() if p.is_file()]+[ROOT/'docs/network-independence.md']
findings=[f for p in paths for f in scanner.inspect_file(p,str(p.relative_to(ROOT)))];assert not findings
report=dict(result='passed_extended_branded_host_and_current_CSS_dispositions',utc=datetime.now(timezone.utc).isoformat(),image=record['image_id'],inventory=record['inventory_digest'],generation=4,additional_runtime_family='addons/web/static/fonts/fonts.scss',decision='Optional report font CDN; actual manifest confines declaration to web.report_assets_common, absent from current reference production CSS. No R1 reference report feature exposed. Future report integration requires local fonts or explicit external policy/requalification.',symbolic_test_host='odoo',inherited_translation_host='service.odoo.co.in',translation_host_ownership_not_asserted=True,production_CSS=css,privacy=dict(known_values=len(values),files=len(paths),findings=0),evidence_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},limits=['Supplements backend-qualification.json, does not erase its earlier finite root-domain scope. Initial24runtime families plus1report-font family reviewed.','Broader URL-host scan is heuristic; arbitrary dynamic/obfuscated hosts/native code/OS/browser background behavior are outside scope.','Current native-form/Labels/two-tab/RTL browser coverage, source-kit/privacy/release closure and final G7 remain. No additional weighted point or acceptance pass.','CSS fetched twice for additional parser verification with exact prior content hashes; no bootstrap/job/lifecycle/100cycle/browser replay.'])
with (OUT/'alias-qualification.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],CSS_assets=len(css),remote_CSS_resources=0,privacy_findings=0)))
