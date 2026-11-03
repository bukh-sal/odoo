"""Primary version comparisons; preserve unresolved findings rather than waive them."""
import collections,hashlib,html,json,re,subprocess
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime,timezone
ROOT=Path.cwd();OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-support-images-02';V=PRIVATE/'vendor'
inv=json.loads((OUT/'inventory.json').read_text());debian=json.loads((ROOT/'.local/g7-release-runtime-audit-01/advisories/debian-tracker.json').read_text())
def numeric(v):return tuple(map(int,v.split('.')))
def clean(s):return ' '.join(html.unescape(re.sub('<[^>]+>',' ',s)).split())
# Enumerate the vendor-reported fixed versions for every installed Alpine origin.
origins=collections.defaultdict(set)
for p in inv['roles']['nginx']['packages']:origins[p['origin']].add(p['version'])
comparisons=[];secfixes=[]
for repository in ['main','community']:
 data=json.loads((V/('alpine-'+repository+'.raw')).read_text())
 for entry in data['packages']:
  p=entry['pkg'];name=p['name']
  if name not in origins:continue
  for fixed,ids in p.get('secfixes',{}).items():
   for installed in sorted(origins[name]):
    assert re.fullmatch('[A-Za-z0-9_.+~-]+',installed) and re.fullmatch('[A-Za-z0-9_.+~-]+',fixed)
    comparisons.append((installed,fixed));secfixes.append(dict(origin=name,installed=installed,fixed=fixed,advisories=ids,repository=repository))
image=inv['roles']['nginx']['image_id'];payload=''.join(a+' '+b+'\n' for a,b in comparisons)
r=subprocess.run(['docker','run','--rm','-i','--name','mp-g7-support-alpine-order-01','--label','com.modular.disposable=mp-g7-support-audit','--network','none','--log-driver','none','--read-only','--cap-drop','ALL','--entrypoint','/bin/sh',image,'-c','while read -r installed fixed; do apk version --test "$installed" "$fixed" || exit 1; done'],input=payload.encode(),capture_output=True,timeout=60)
(PRIVATE/'alpine-comparisons02.stdout').write_bytes(r.stdout);(PRIVATE/'alpine-comparisons02.stderr').write_bytes(r.stderr);assert r.returncode==0
order=r.stdout.decode().splitlines();assert len(order)==len(secfixes)
for row,comparison in zip(secfixes,order):assert comparison in ['<','=','>'];row['installed_before_fix']=comparison=='<'
# PostgreSQL vendor table, actual server16.15 and clientlib15.19.
class Table(HTMLParser):
 def __init__(self):super().__init__();self.rows=[];self.row=[];self.cell=None
 def handle_starttag(self,t,a):
  if t=='tr':self.row=[]
  if t in ('td','th'):self.cell=[]
 def handle_data(self,d):
  if self.cell is not None:self.cell.append(d)
 def handle_endtag(self,t):
  if t in ('td','th') and self.cell is not None:self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
  if t=='tr' and self.row:self.rows.append(self.row)
t=Table();t.feed((V/'postgres.raw').read_text());pg=[]
for row in t.rows:
 if len(row)!=5 or not re.search(r'CVE-\d+-\d+',row[0]):continue
 for role,major,installed in [('server16',16,'16.15'),('application_libpq15',15,'15.19')]:
  affected=[int(v.strip()) for v in row[1].split(',') if v.strip().isdigit()]
  if major not in affected:continue
  fixes=[v for v in re.findall(r'\d+\.\d+',row[2]) if v.startswith(str(major)+'.')];assert len(fixes)==1
  if role.startswith('application') and not row[3].startswith('client'):continue
  pg.append(dict(cve=re.search(r'CVE-\d+-\d+',row[0]).group(),role=role,installed=installed,fixed=fixes[0],installed_before_fix=numeric(installed)<numeric(fixes[0])))
# Native bundled crypto and system crypto are separate libraries. Debian backports
# must be evaluated using source package revision, not ssl.OPENSSL_VERSION text.
crypto=[]
for name,series,installed in [('openssl4','4.0','4.0.3'),('openssl3','3.0','3.0.22'),('openssl35','3.5','3.5.9')]:
 text=(V/(name+'.raw')).read_text();blocks=re.split(r'<h2 id="(CVE-\d+-\d+)">',text)
 for i in range(1,len(blocks),2):
  ident,block=blocks[i:i+2]
  ranges=re.findall(r'<li>from ([^<]+?) before ([^<]+?)\s*</li>',block)
  for start,end in ranges:
   start=start.strip();end=end.strip()
   if not start.startswith(series+'.'):continue
   assert re.fullmatch(r'\d+\.\d+\.\d+',start) and (not end or re.fullmatch(r'\d+\.\d+\.\d+',end))
   affected=numeric(start)<=numeric(installed)<numeric(end) if end else None
   backport=debian.get('openssl',{}).get(ident,{}).get('releases',{}).get('bookworm',{}) if series=='3.0' else None
   crypto.append(dict(cve=ident,series=series,installed=installed,introduced=start,fixed=end,upstream_range_matches=affected,Debian_bookworm=backport))
nginx=[]
for block in re.findall(r'<li><p>(.*?)</p></li>',(V/'nginx.raw').read_text(),re.S):
 ids=sorted(set(re.findall(r'CVE-\d+-\d+',block)))
 if not ids:continue
 text=clean(block);m=re.search(r'Not vulnerable: (.*?) Vulnerable:',text)
 if not m:continue
 fixed=re.findall(r'(?<![\d.])(\d+\.\d+\.\d+)\+',m.group(1));assert fixed,(ids,m.group(1))
 nginx.append(dict(cves=ids,installed='1.30.6',fixed_branches=fixed,fixed_in_same_or_prior_branch=any(numeric(v)<=numeric('1.30.6') for v in fixed)))
assert pg and crypto and nginx and secfixes
report=dict(result='primary_version_comparison_completed_findings_require_review',utc=datetime.now(timezone.utc).isoformat(),alpine=dict(installed_origins=len(origins),vendor_secfix_comparisons=len(secfixes),published_fixes_newer_than_installed=[r for r in secfixes if r['installed_before_fix']],rows=secfixes),postgres=dict(comparisons=pg,newer_fixes=[r for r in pg if r['installed_before_fix']]),openssl=dict(comparisons=crypto,upstream_range_matches=[r for r in crypto if r['upstream_range_matches'] is not False]),nginx=dict(comparisons=nginx,unresolved=[r for r in nginx if not r['fixed_in_same_or_prior_branch']]),limits=['Current vendor fixed-range snapshot; absent/undisclosed issues are not disproven.','Alpine secfixes records published fixes, not all potential unfixed vulnerabilities. PG platform OS/debian source still separate.','OpenSSL3.0.22 Debian revision must meet backport fixed version; upstream version match alone is not a vulnerability conclusion.','No blanket final security qualification; broader OS/reachability/vendored/license/network/history/archive/secret checks remain.'])
with (OUT/'vendor-version-review.json').open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
print(json.dumps(dict(alpine_comparisons=len(secfixes),alpine_newer=len(report['alpine']['published_fixes_newer_than_installed']),pg_comparisons=len(pg),pg_newer=len(report['postgres']['newer_fixes']),openssl_range_matches=[r['cve'] for r in report['openssl']['upstream_range_matches']],nginx_advisories=len(nginx),nginx_unresolved=len(report['nginx']['unresolved']))))
