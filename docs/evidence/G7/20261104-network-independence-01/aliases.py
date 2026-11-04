"""Broader Odoo-branded URL hosts and actual served CSS; no app/session mutation."""
import hashlib,json,re,subprocess,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path.cwd();OUT=Path(__file__).parent
def load(p):return json.loads(p.read_bytes())
record=load(ROOT/'.local/g7-ui-qualification-01/browser-input.json');target=load(ROOT/'.local/release-kit-rehearsal/private/reference/operator/target.json');assert target['image_id']==record['image_id'] and target['generation']==4
script=r'''
import ast,hashlib,json,pathlib,re
root=pathlib.Path('/opt/modular');inventory=json.loads((root/'distribution-inventory.json').read_bytes());records=[]
pattern=re.compile(r'(?i)https?://([a-z0-9_.-]+)')
for name,digest in inventory['files'].items():
 p=root/name
 if p.suffix.lower() not in {'.py','.js','.xml','.scss','.css','.html','.json','.po','.txt','.rst','.md'}:continue
 data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==digest
 try:text=data.decode('utf8')
 except UnicodeError:continue
 matches=[]
 for n,line in enumerate(text.splitlines(),1):
  hosts=sorted(set(m.group(1).lower() for m in pattern.finditer(line) if any(v in m.group(1).lower() for v in ['odoo','openerp']) and not m.group(1).lower().endswith(('.odoo.com','.odoo.net','.openerp.com','.openerp.net')) and m.group(1).lower() not in ['odoo.com','odoo.net','openerp.com','openerp.net']))
  if hosts:matches.append(dict(line=n,hosts=hosts))
 if matches:records.append(dict(path=name,sha256=digest,matches=matches))
manifest=ast.literal_eval((root/'addons/web/__manifest__.py').read_text())
font_bundles=[name for name,items in manifest['assets'].items() if 'web/static/fonts/fonts.scss' in items]
print(json.dumps(dict(records=records,remote_font_declaring_bundles=font_bundles)))
'''
response=json.loads(subprocess.check_output(['docker','exec',target['worker_id'],'/venv/bin/python','-c',script],stderr=subprocess.PIPE,timeout=60))
assert response['remote_font_declaring_bundles']==['web.report_assets_common']
samples=load(OUT.parent/'20261104-ui-qualification-01/performance-result.json');paths=sorted(set(x['path'] for x in samples['production_assets'] if x['path'].endswith('.css')));css=[]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));base=urlsplit(record['base'])
for path in paths:
 assert path.startswith('/web/assets/')
 request=urllib.request.Request('http://127.0.0.1:'+str(base.port)+path,headers={'Host':base.netloc})
 with opener.open(request,timeout=15) as result:
  data=result.read();assert result.status==200 and 'text/css' in result.headers['Content-Type']
 hosts=sorted(set(re.findall(rb'(?i)https?://([a-z0-9_.-]+)',data)));css.append(dict(path=path,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),URL_hosts=[x.decode() for x in hosts]))
 assert b'fonts.odoocdn.com' not in data
report=dict(result='collected_extended_Odoo_host_aliases_and_current_production_CSS',utc=datetime.now(timezone.utc).isoformat(),image=record['image_id'],inventory=record['inventory_digest'],generation=4,**response,production_CSS=css,limits=['Read-only actual retained-source URL-host scan adds branded aliases such as odoocdn and od oo.github.io beyond initial root-domain detector. Explicit per-family disposition required before final qualification.','Only actual production CSS paths observed by the completed shell run are fetched, through local loopback/canonical Host, without cookies or credentials. No additional browser flow or business mutation.','Optional report asset bundle is distinct from ordinary shell/reference/native view assets. A report feature would require local-font substitution or explicit external policy and requalification.'])
with (OUT/'extended-hosts-and-CSS.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(result=report['result'],source_paths=[r['path'] for r in response['records']],font_bundles=response['remote_font_declaring_bundles'],CSS_assets=len(css),CSS_odoocdn_references=0)))
