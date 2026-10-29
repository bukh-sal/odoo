"""Classify retained Odoo-hosted source references without contacting those services."""
import collections,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent
inventory=json.loads((ROOT/'.local/g5-provenance/runtime-observation.json').read_text())['inventory'];records=[]
# Start with rg, then restrict candidates to the exact retained runtime source.
result=subprocess.run(['rg','--files-with-matches','--null','--no-messages',r'https?://[^\s"<>]*odoo\.(com|sh|io)','addons/web','addons/auth_totp','odoo/addons/base'],capture_output=True,cwd=ROOT,timeout=30)
assert result.returncode in [0,1]
for raw in result.stdout.split(b'\0'):
    if not raw:continue
    path=ROOT/raw.decode();name=path.relative_to(ROOT).as_posix()
    if name not in inventory['files']:continue
    text=path.read_text(encoding='utf8',errors='replace')
    for m in re.finditer(r'https?://(?:[\w-]+\.)*odoo\.(?:com|sh|io)(?:/[^\s<>"\x27)]*)?',text):
        url=m.group();line=text.count('\n',0,m.start())+1
        if '/tests/' in name or '/hoot/' in name:category='test or developer documentation fixture';behavior='Not a reference application service dependency.'
        elif 'documentation' in url:category='user-facing documentation link';behavior='Retain attribution/help target; optional user navigation.'
        elif 'accounts.odoo.com' in url:category='optional account integration';behavior='Stock native endpoint/menu source retained; platform custom root does not expose the stock account menu. Not required by local native authentication.'
        elif 'ir_module_module.xml' in name or any(v in url for v in ['/buy','/editions','/upgrade','/app/']):category='optional commercial or catalog user-facing link';behavior='Upstream catalog/stock settings metadata retained; excluded ERP/Enterprise implementation is not installed. Neutral platform manager uses curated artifacts.'
        else:category='branding or attribution user-facing link';behavior='Retained upstream template/PWA metadata, not a server boot dependency. Full reference-browser network/branding review remains G7.'
        records.append(dict(path=name,line=line,url=url,category=category,behavior=behavior,source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
value=dict(result='classified',references=len(records),categories=dict(collections.Counter(r['category'] for r in records)),records=records,server_network='Qualified app/database are on the project internal Docker network; no outbound network and cron0. Optional IAP/rpc/base_import_module/web_unsplash implementations are excluded by the curated addon allowlist.',limits=['Static retained-source classification, not a claim that every browser can never follow an external link.','No call to Odoo-hosted account/catalog/buy/support services. Build-time pinned package downloads are separately recorded.','G7 must verify final browser/runtime network behavior and user-facing remnants after G6; no wholesale frontend or upstream auth rewrite.'])
(OUTPUT/'retained-product-ties.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps(dict(result='classified',references=len(records),categories=value['categories'])))
