"""Retain public advisory evidence before compatibility/remediation decisions."""
import concurrent.futures,hashlib,json,re,urllib.request
from datetime import datetime,timezone
from pathlib import Path
OUT=Path(__file__).parent;ROOT=OUT.parents[3];PRIVATE=ROOT/'.local/g7-release-runtime-audit-01/advisories'
index=json.loads((OUT/'advisory-matches.json').read_text());ids=index['unique_advisories'];destination=PRIVATE/'details';assert not destination.exists();destination.mkdir()
def one(ident):
 assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,200}',ident) and '..' not in ident
 request=urllib.request.Request('https://api.osv.dev/v1/vulns/'+ident,headers={'User-Agent':'modular-platform-local-release-audit/1'})
 with urllib.request.urlopen(request,timeout=30) as response:raw=response.read()
 data=json.loads(raw);assert data['id']==ident
 (destination/(ident+'.json')).write_bytes(raw)
 return dict(id=ident,aliases=data.get('aliases',[]),withdrawn=data.get('withdrawn'),published=data.get('published'),modified=data.get('modified'),severity=data.get('severity',[]),affected=data.get('affected',[]),references=data.get('references',[]),database_specific=data.get('database_specific',{}),raw_sha256=hashlib.sha256(raw).hexdigest())
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
 pending={pool.submit(one,ident):ident for ident in ids}
 for future in concurrent.futures.as_completed(pending):
  results.append(future.result())
  if len(results)%40==0:print(json.dumps(dict(advisory_details_collected=len(results),total=len(ids))),flush=True)
value=dict(result='advisory_details_collected_triage_pending',utc=datetime.now(timezone.utc).isoformat(),source='https://api.osv.dev/v1/vulns/{id}',records=sorted(results,key=lambda v:v['id']),limits=['Raw full advisory documents retained privately; only factual ranges/IDs/severity/references indexed here.','Untriaged matches may be aliases, withdrawn or irrelevant to installed/runtime use. No security pass or affectedness conclusion.','OS/vendor runtimes and vendored dependencies remain separate.'])
path=OUT/'advisory-details.json';assert not path.exists();path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(result=value['result'],records=len(results),withdrawn=sum(bool(r['withdrawn']) for r in results))))
