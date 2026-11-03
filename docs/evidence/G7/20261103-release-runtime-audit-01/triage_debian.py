"""Match primary Bookworm status to observed versions using native dpkg ordering."""
import collections,hashlib,json,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent;PRIVATE=ROOT/'.local/g7-release-runtime-audit-01/advisories'
source=json.loads((OUT/'debian-source-tracker.json').read_text());matches=json.loads((OUT/'advisory-matches.json').read_text());details=json.loads((OUT/'advisory-details.json').read_text());byid={r['id']:r for r in details['records']}
rows=[]
for row in matches['matches']:
 if row['query']['package']['ecosystem']!='Debian:12':continue
 name=row['query']['package']['name']
 for advisory in row['advisories']:
  ident=advisory['id'];cve=ident.removeprefix('DEBIAN-');record=source['selected'][name][cve];release=record['releases'].get('bookworm');assert release
  rows.append(dict(package=name,installed_version=row['query']['version'],roles=row['roles'],advisory_id=ident,cve=cve,status=release['status'],urgency=release['urgency'],fixed_version=release.get('fixed_version'),nodsa_reason=release.get('nodsa_reason'),vendor_reference='https://security-tracker.debian.org/tracker/'+cve,OSV_withdrawn=byid[ident]['withdrawn']))
comparisons=[dict(installed=r['installed_version'],fixed=r['fixed_version']) for r in rows if r['fixed_version'] and r['fixed_version']!='0']
image=json.loads((OUT/'application-index.json').read_text())['image_id']
code="import json,subprocess,sys;p=json.load(sys.stdin);r=[]\nfor v in p:\n c=subprocess.run(['dpkg','--compare-versions',v['installed'],'lt',v['fixed']]);assert c.returncode in (0,1);r.append(dict(v,installed_before_fix=c.returncode==0))\nprint(json.dumps(r))"
args=['docker','run','--rm','-i','--name','mp-g7-release-audit-debian-order-01','--label','com.modular.disposable=mp-g7-release-audit','--log-driver','none','--network','none','--read-only','--user','10001:10001','--cap-drop','ALL','--entrypoint','/venv/bin/python',image,'-c',code]
result=subprocess.run(args,input=json.dumps(comparisons).encode(),capture_output=True,timeout=30,check=True);(PRIVATE/'debian-version-comparisons.json').write_bytes(result.stdout);comp={(r['installed'],r['fixed']):r['installed_before_fix'] for r in json.loads(result.stdout)}
for row in rows:
 fixed=row['fixed_version']
 row['installed_before_published_fix']=comp[(row['installed_version'],fixed)] if fixed and fixed!='0' else None
 row['triage']='withdrawn' if row['OSV_withdrawn'] else 'published_fix_newer_than_installed' if row['installed_before_published_fix'] else 'vendor_open_unimportant_review' if row['status']=='open' and row['urgency']=='unimportant' else 'vendor_open_review' if row['status']=='open' else 'vendor_undetermined_review' if row['status']=='undetermined' else 'version_status_review'
counts=collections.Counter(r['triage'] for r in rows);fixes=[r for r in rows if r['installed_before_published_fix']]
report=dict(result='primary_Debian_status_version_triage_review_pending',utc=datetime.now(timezone.utc).isoformat(),source_tracker_sha256=source['sha256'],matched_source_advisory_pairs=len(rows),counts=dict(counts),published_fixes_newer_than_installed=fixes,rows=rows,limits=['Uses actual Debian source versions and dpkg ordering; no unimportant/nodsa status automatically means safe or waived.','Remaining open/undetermined/reachability/binary presence/PG/nginx/vendored scope and remediation decisions require review.','This is not final security qualification.'])
with (OUT/'debian-status-triage.json').open('x',encoding='utf8') as stream:json.dump(report,stream,indent=2);stream.write('\n')
print(json.dumps(dict(result=report['result'],counts=dict(counts),newer_published_fixes=[dict(package=r['package'],installed=r['installed_version'],fixed=r['fixed_version'],cve=r['cve']) for r in fixes])))
