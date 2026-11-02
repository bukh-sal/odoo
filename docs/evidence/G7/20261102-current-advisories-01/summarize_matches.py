"""Group aliases for review; this does not assert installed-code exploitability."""
import json,re
from pathlib import Path
OUT=Path(__file__).parent
matches=json.loads((OUT/'python-node-advisory-matches.json').read_text());details=json.loads((OUT/'python-node-advisory-details.json').read_text())['records']
parent={}
def find(value):
 parent.setdefault(value,value)
 if parent[value]!=value:parent[value]=find(parent[value])
 return parent[value]
def join(a,b):parent[find(b)]=find(a)
for r in details:
 find(r['id'])
 for alias in r['aliases']:join(r['id'],alias)
groups={}
for value in list(parent):groups.setdefault(find(value),set()).add(value)
canonical={root:next(iter(sorted(n for n in values if n.startswith('CVE-'))),sorted(values)[0]) for root,values in groups.items()}
byid={r['id']:r for r in details};rows=[]
for row in matches['matches']:
 if not row['advisories']:continue
 records=[byid[a['id']] for a in row['advisories']];name=row['query']['package']['name'];fixes=set();git_fixes=set()
 for r in records:
  for affected in r['affected']:
   package=affected.get('package',{});normalized=re.sub('[-_.]+','-',package.get('name','')).lower()
   if package.get('ecosystem')!=row['query']['package']['ecosystem'] or normalized!=name:continue
   for interval in affected.get('ranges',[]):
    for event in interval.get('events',[]):
     if 'fixed' in event:(git_fixes if interval.get('type')=='GIT' else fixes).add(event['fixed'])
 rows.append(dict(package=name,installed_version=row['query']['version'],roles=row['roles'],matched_record_count=len(records),alias_components=sorted({canonical[find(r['id'])] for r in records}),reported_fixed_versions=sorted(fixes),reported_fixed_git_commits=sorted(git_fixes),severity_labels=sorted({r['database_specific'].get('severity') for r in records if r['database_specific'].get('severity')}),references=sorted({ref['url'] for r in records for ref in r['references'] if ref.get('type')=='ADVISORY'}),disposition='review_required_not_yet_classified'))
result=dict(result='alias_and_range_review_index_not_security_pass',matched_package_version_entries=len(rows),raw_records=len(details),alias_connected_components=len(groups),packages=rows,source='https://api.osv.dev/v1/querybatch',limits=['Alias components are a review aid, not a count of independently exploitable vulnerabilities.','Reported fixed versions span advisory branches and are not selected dependency recommendations.','Installed-code reachability, primary advisory confirmation and actual compatibility tests remain before remediation or a release decision.'])
path=OUT/'triage-index.json';assert not path.exists();path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(package_version_entries=len(rows),raw_records=len(details),alias_components=len(groups),review_pending=True)))
