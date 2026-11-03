"""Public catalog and parent directory integrity without claiming confidentiality."""
from datetime import datetime,timezone
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[4];OUTPUT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.operator_os import _windows_acl,current_identity

def main():
 dest=OUTPUT/'windows-catalog-parent-integrity.json';assert not dest.exists(),'Existing audit is terminal; use it rather than repeating'
 owner=current_identity().removeprefix('windows-sid:');allowed={owner,'S-1-5-18','S-1-5-32-544','S-1-3-4'};mask=0x2|0x4|0x10|0x40|0x100|0x10000|0x40000|0x80000;paths=[ROOT,ROOT/'.local',ROOT/'.local/g7-fresh-release-01',ROOT/'.local/g7-fresh-release-01/target21',ROOT/'.local/g7-fresh-release-01/target21/operator',ROOT/'.local/g7-fresh-release-01/target21/operator/catalog',*(ROOT/'.local/g7-fresh-release-01/target21/operator/catalog').rglob('*')];rows=[];bad=[]
 for p in paths:
  a=_windows_acl(p);name=p.relative_to(ROOT).as_posix();rows.append(dict(path=name,**a))
  if a['owner']!=owner:bad.append(dict(path=name,reason='unexpected owner'))
  for rule in a['rules']:
   if rule['sid'] not in allowed and rule['type']=='Allow' and rule['rights']&mask:bad.append(dict(path=name,reason='untrusted mutation rights',sid=rule['sid']))
 report=dict(result='passed' if not bad else 'failed_review_required',utc=datetime.now(timezone.utc).isoformat(),paths=len(rows),rows=rows,violations=bad,limits=['Public metadata may be readable; independent configuration/catalog and parent directories must not permit untrusted mutation or delete/replace.']);dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=report['result'],paths=len(rows),violations=bad)))
if __name__=='__main__':main()
